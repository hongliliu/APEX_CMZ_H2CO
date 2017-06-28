import numpy as np
from astropy import units as u
from pyspeckit_fitting import (simplemodel, simplemodel2, simple_fitter,
                               simple_fitter2, simple_fitter3)
from full_cubes import cube_merge_high
from masked_cubes import (cube303, cube303sm, cube303m, cube321m, cube303msm,
                          cube321msm, cube321, cube321sm)
from noise import (noise, noise_cube, sm_noise, cube303nm, cube303nmsm,
                   cube321nm, cube321nmsm)
import pyspeckit
from astrodendro import Dendrogram
from astropy.utils.console import ProgressBar
import paths
import pylab as pl
import pyregion

regs = pyregion.open(paths.rpath('spectral_apertures.reg'))
regdict = {r.attr[1]['text']:r for r in regs}

def get_subregion_pcube(cube303m, cube303, cube321, region):
    #scube = cube_merge_high.subcube_from_ds9region(pyregion.ShapeList([region]))
    scube303m = cube303m.subcube_from_ds9region(pyregion.ShapeList([region]))
    scube303 = cube303.subcube_from_ds9region(pyregion.ShapeList([region]))
    scube321 = cube321.subcube_from_ds9region(pyregion.ShapeList([region]))
    # TODO: get error map
    #pcube = pyspeckit.Cube(cube=scube)
    pcube303 = pyspeckit.Cube(cube=scube303)
    pcube303.xarr.refX = cube303.wcs.wcs.restfrq
    pcube303.xarr.refX_unit = 'Hz'
    pcube321 = pyspeckit.Cube(cube=scube321)
    pcube321.xarr.refX = cube321.wcs.wcs.restfrq
    pcube321.xarr.refX_unit = 'Hz'
    pcube = pyspeckit.CubeStack([pcube303,pcube321,])
    pcube.specfit.Registry.add_fitter('h2co_simple', simple_fitter3, 4,
                                      multisingle='multi')
    pcube.xarr.refX = cube303m.wcs.wcs.restfrq
    pcube.xarr.refX_unit = 'Hz'
    return pcube, scube303m


# cold, narrow
# pc = do_1comp_region('G1.12-0.10', vrange=[-40,0], startpoint=(5,5))
# pc = do_1comp_region('G1.00-0.02', vrange=[20,130], startpoint=(5,5))
# pc = do_1comp_region('G0.67-0.10', vrange=[00,50], startpoint=(5,5))

def do_1comp_region(region='G0.47-0.07box', vrange=[50,125], minpeak=0.22,
                    startpoint=(22,6), **kwargs):
    pc,c3 = get_subregion_pcube(cube303, cube303, cube321, regdict[region])
    c3slab = c3.spectral_slab(vrange[0]*u.km/u.s, vrange[1]*u.km/u.s)
    moments = c3slab.moment1(axis=0)
    peak = c3slab.max(axis=0)
    vguesses = moments
    vguesses[vguesses.value<vrange[0]] = np.mean(vrange)*vguesses.unit
    vguesses[vguesses.value>vrange[1]] = np.mean(vrange)*vguesses.unit
    mask = peak.value>minpeak
    vguesses[~mask] = np.nan
    do_pyspeck_fits_1comp(pc, m1=vguesses, vrange=vrange,
                          peaks=peak,
                          limits=[(0,20), vrange,(1,40),(0,1)],
                          guesses=[np.nan,np.nan,5,0.5],
                          start_from_point=startpoint,
                          **kwargs)
    print "Mean ratio: {0:0.3f}".format((pc.parcube[0,:,:]*pc.parcube[3,:,:]).sum()/(pc.parcube[0,:,:].sum()))
    return pc


def do_pyspeck_fits_1comp(pcube, cube303m=None, vguesses='moment',
                          guesses=[1,None,5,0.5,0.7,1], vrange=(-105,125),
                          peaks=None,
                          m1=None,
                          limits=[(0,20), (-105,125),(1,40),(0,1),(0.3,1.1),(0,1e5)],
                          start_from_point=(0,0),
                          **kwargs):

    if m1 is None:
        m1 = cube303m.moment1(axis=0).to(u.km/u.s)
    if vguesses == 'moment':
        guesses_simple = np.array([guesses[0:1]+[x]+guesses[2:]
                                   for x in m1.value.flat]).T.reshape((len(guesses),)+m1.shape)
        bad = (guesses_simple[1,:,:] < vrange[0]) | (guesses_simple[1,:,:] > vrange[1])
        guesses_simple[1,bad] = 25
    else:
        guesses_simple = guesses

    g0 = guesses_simple

    if peaks is not None:
        # Wow, this is complicated
        # First, guesses needs to be reshaped to have the n_guesses as trailing axis
        # Then, it needs to be remade to have the first element be the appropriate peak...
        flatguesses = guesses_simple.reshape(guesses_simple.shape[0],
                                             np.prod(guesses_simple.shape[1:])).T
        guesses_simple = np.array([[peak]+g[1:].tolist()
                                   for peak,g in zip(peaks.value.flat,
                                                     flatguesses,)
                                  ]
                                 ).T.reshape((len(guesses),)+peaks.shape)
    # Can't accept guesses being wrong, and I've made too many mistakes...
    assert np.all(np.nan_to_num(g0[1:,0,0]) == np.nan_to_num(guesses_simple[1:,0,0]))
    assert np.all(np.nan_to_num(g0[1:,start_from_point[1],
                                   start_from_point[0]]) ==
                  np.nan_to_num(guesses_simple[1:,start_from_point[1],
                                               start_from_point[0]]))

    # Need to show pcube which pixels to ignore: m1 has nans
    pcube.mapplot.plane = m1.value
    pcube.fiteach(fittype='h2co_simple', multifit=True,
                  guesses=guesses_simple,
                  limited=[(True,True)] * len(guesses_simple),
                  limits=limits,
                  multicore=8,
                  integral=False,
                  **kwargs
                 )

    #pcube.mapplot(estimator=0)
    pcube_orig = pcube.parcube.copy()
    pcube2 = remove_bad_pars(pcube.parcube, pcube.errcube, len(guesses),
                             min_nsig=4)

def do_the_brick(vrange=[-20,125], minpeak=0.22):
    pc,c3 = get_subregion_pcube(cube303, cube303, cube321, regdict['BrickBox'])
    c3slab = c3.spectral_slab(vrange[0]*u.km/u.s, vrange[1]*u.km/u.s)
    moments = c3slab.moment1(axis=0)
    peak = c3slab.max(axis=0)
    vguesses = moments
    vguesses[vguesses.value<vrange[0]] = np.nan
    vguesses[vguesses.value>vrange[1]] = np.nan
    mask = peak.value>minpeak
    vguesses[~mask] = np.nan
    do_pyspeck_fits_2comp(pc, cube303m=c3, m1=vguesses, vrange=vrange,
                          limits=[(0,20), vrange,(1,40),(0,1)],
                          guesses_simple=[1,15,5,0.5] +
                                         [1,36,5,0.5]
                         )
    return pc


def do_pyspeck_fits_2comp(pcube, cube303m=None, vrange=(-105,125),
                          m1=None,
                          guesses_simple=[1,15,5,0.5,0.7,1] +
                          [1,36,5,0.5,0.7,1],
                          limits=[(0,20),(-105,125),(1,40),(0,1),(0.3,1.1),(0,1e5)],
                         ):

    if m1 is None:
        m1 = cube303m.moment1(axis=0).to(u.km/u.s)
    # Need to show pcube which pixels to ignore: m1 has nans
    pcube.mapplot.plane = m1.value
    pcube.fiteach(fittype='h2co_simple', multifit=True,
                        guesses=guesses_simple,
                        limited=[(True,True)] * len(guesses_simple),
                        limits=limits,
                        multicore=8,
                 )

    pcube.mapplot(estimator=0)
    pcube_orig = pcube.parcube.copy()
    pcube2 = remove_bad_pars(pcube.parcube, pcube.errcube, len(guesses_simple),
                             min_nsig=4)
    return pcube2

def remove_bad_pars(parcube, errcube, npars, min_nsig=3):
    """
    Excise bad fits from a parameter fit cube (from pyspeckit)
    """
    if parcube.shape[0] % npars != 0:
        raise ValueError("Invalid # of parameters {0},"
                         "it should divide evenly "
                         "into {1}".format(npars, parcube.shape[0]))
    assert errcube.shape == parcube.shape

    ncomp = parcube.shape[0]/npars
    for jj in range(ncomp):
        shift = jj*npars
        bad = ((parcube[0+shift,:,:] < min_nsig*errcube[0+shift,:,:]) |
               (errcube[3+shift,:,:] == 0))
        parcube[jj*npars:(jj+1)*npars,bad] = 0
    return parcube


def do_g047_box():
    """ old example; use do_1comp now"""
    # That's awesome.
    pc,c3 = get_subregion_pcube(cube303, cube303, cube321, regdict['G0.47-0.07box'])
    c3slab = c3.spectral_slab(50*u.km/u.s, 125*u.km/u.s)
    moments = c3slab.moment1(axis=0)
    peak = c3slab.max(axis=0)
    vguesses = moments
    vguesses[vguesses.value<50] = np.nan
    vguesses[vguesses.value>125] = np.nan
    mask = peak.value>0.22
    vguesses[~mask] = np.nan
    do_pyspeck_fits_1comp(pc, m1=vguesses, vrange=(50,125),
                          limits=[(0,20), (50,125),(1,40),(0,1)],
                          guesses=[1,None,5,0.5],
                          start_from_point=(22,6))
    return pc

