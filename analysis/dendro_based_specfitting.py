"""
Use dendrograms as seeds...
"""
from astropy.table import Table
from pyspeckit_fitting import simple_fitter, simple_fitter2
from full_cubes import pcube_merge_high, cube_merge_high
from paths import mpath,hpath
from dendrograms import dend,dendsm,catalog,catalog_sm
import numpy as np
from astropy.utils.console import ProgressBar
from astropy import log

def get_all_indices(dendrogram):
    inds = []
    for structure in dendrogram.trunk:
        if structure.parent is None: # should be true for all
            inds.append(structure.indices())
    allzinds,allyinds,allxinds = [np.concatenate(ii)
                                  for ii in zip(*inds)]
    unique_inds = set(zip(allxinds, allyinds))
    return np.array(list(unique_inds))

def match_position(position, structure):
    x,y = position
    return (x in structure.indices()[2] and y in structure.indices()[1])

def smallest_match(position, structure):
    """
    Given a position and a structure in which at least one structure in the
    tree contains a match, return the smallest structure that matches that
    position
    """
    if match_position(position, structure):
        if structure.children:
            c1 = smallest_match(position, structure.children[0])
            if c1 is not structure:
                return c1
            return smallest_match(position, structure.children[1])
        else:
            return structure
    else:
        return structure.parent

def find_smallest_overlapping_branches(position, dendrogram):
    matched_roots = [d
                      for d in dendrogram.trunk
                      if d.parent is None and
                      match_position(position, d)
                     ]
    matched_branches = [smallest_match(position, d) for d in matched_roots]
    return matched_branches

def get_guesses(index, catalog):
    amp,vc,vsig,r = catalog['Smean303', 'v_cen', 'v_rms',
                            'r303321'][index].columns.values()
    glon = [xc - 360 if xc > 180 else xc
            for xc in catalog['x_cen']]
    # TODO: make sure the velocity units remain consistent
    # The logic here is to filter out things at vlsr<-50 km/s that are not in Sgr C;
    # these are mostly other lines in Sgr B2
    return [pars for pars,glon in zip(zip(*[x.data for x in [amp,vc/1e3,vsig,r,amp]]),
                                      glon)
            if glon < 0 or (glon > 0 and pars[1] > -50)]

def clean_catalog(catalog):
    """
    Remove cataloged clumps that are not H2CO
    """
    bad = ((catalog['v_cen'] < -50) &
           (catalog['x_cen']>0) &
           (catalog['x_cen']<180))
    raise # this is a bad idea
    return catalog[~bad]

pcube_merge_high.Registry.add_fitter('h2co_simple', simple_fitter, 5,
                                     multisingle='multi')
pcube_merge_high.Registry.add_fitter('h2co_simple2', simple_fitter2, 6,
                                     multisingle='multi')

def fit_position(position, dendrogram=dend, pcube=pcube_merge_high,
                 catalog=catalog, plot=True, order=1, second_ratio=False,
                 verbose=False):
    branches = find_smallest_overlapping_branches(position, dendrogram)
    branch_ids = [l.idx for l in branches]
    if len(branch_ids) == 0:
        log.error("Invalid position given: {0}.  No branches found.".format(position))
        raise
        return
    guess = get_guesses(branch_ids, catalog)

    sp = pcube.get_spectrum(position[0], position[1])

    if second_ratio:
        guesses = [p
                   for g in guess if g[0]>0 and g[3]>0
                   for p in (g[:4]+(1,g[4]))]
        limits = [a
                  for g in guess if g[0]>0 and g[3]>0
                  for a in ((g[0]*0.1, g[0]/0.1),
                            (g[1]-15, g[1]+15),
                            (max(g[2]-5,1), g[2]+10),
                            (g[3]*0.1, g[3]/0.1),
                            (0.3, 1.1), # physical limits
                            (g[4]*0.05, g[4]/0.05))
                 ]
        fittype = 'h2co_simple2'
        assert len(guesses) % 6 == 0
        assert len(limits) % 6 == 0
    else:
        guesses = [p for g in guess if g[0]>0 and g[3]>0 for p in g]
        limits = [a
                  for g in guess if g[0]>0 and g[3]>0
                  for a in ((g[0]*0.1, g[0]/0.1),
                            (g[1]-15, g[1]+15),
                            (max(g[2]-5,1), g[2]+10),
                            (g[3]*0.1, g[3]/0.1),
                            (g[4]*0.05, g[4]/0.05))
                 ]
        fittype = 'h2co_simple'
        assert len(guesses) % 5 == 0
        assert len(limits) % 5 == 0

    if len(guesses) == 0:
        log.info("Position {0},{1} has no guesses.".format(position[0],
                                                           position[1]))
        log.info("Guess was: {0}".format(guess))
        return

    sp.specfit(fittype=fittype, multifit=True,
               guesses=guesses,
               limited=[(True,True)] * len(guesses),
               limits=limits,
               verbose=verbose,
              )

    assert len(guesses) % (5+second_ratio) == 0
    assert len(sp.specfit.parinfo) % (5+second_ratio) == 0

    if plot:
        sp.plotter()
        sp.specfit.plot_fit()
        sp.baseline(excludefit=True, subtract=False, highlight_fitregion=True, order=order)
    else:
        sp.baseline(excludefit=True, subtract=False, order=order, verbose=verbose)
        
    sp.specfit(fittype=fittype, multifit=True,
               guesses=guesses,
               limited=[(True,True)] * len(guesses),
               limits=limits,
               verbose=verbose,
              )

    assert len(guesses) % (5+second_ratio) == 0
    assert len(sp.specfit.parinfo) % (5+second_ratio) == 0

    if plot:
        sp.plotter()
        sp.specfit.plot_fit()
        sp.baseline.plot_baseline()

    return sp

def fit_all_positions(dendrogram=dend, pcube=pcube_merge_high, catalog=catalog,
                      order=1, second_ratio=False):
    positions = get_all_indices(dendrogram)

    def get_fitvals(p, plot=False, order=order, second_ratio=second_ratio):
        result = fit_position(p, dendrogram=dendrogram, catalog=catalog,
                              pcube=pcube,
                              plot=False, order=order,
                              second_ratio=second_ratio)
        if result is None:
            return
        return result.specfit.parinfo.values, result.specfit.parinfo.errors

    results = [get_fitvals(p, plot=False, order=order,
                           second_ratio=second_ratio)
               for p in ProgressBar(positions)]
    bad_positions = [p for p,r in zip(positions,results) if r is None]
    positions2 = [p for p,r in zip(positions,results) if r is not None]
    results2 = [r for r in results if r is not None]

    return positions2,results2,bad_positions

def pars_to_maps(positions, parvalues, shape=pcube_merge_high.cube.shape[1:]):

    maxlen = max(len(r) for r in parvalues)

    if maxlen % 6 == 0:
        names = ['AMPLITUDE', 'VELOCITY', 'WIDTH', 'RATIO321303X',
                 'RATIO322321X', 'AMPCH3OH']
        n = 6
    elif maxlen % 5 == 0:
        names = ['AMPLITUDE', 'VELOCITY', 'WIDTH', 'RATIO321303X',
                 'AMPCH3OH']
        n = 5
    else:
        raise

    maps = []
    for jj in range(maxlen / n):
        for ii in xrange(n):
            arr = np.zeros(shape)
            for p,r in zip(positions,parvalues):
                ind = ii + jj*n
                if len(r) > ind:
                    arr[p[1], p[0]] = r[ind]
            maps.append(arr)
            hdu = fits.PrimaryHDU(data=arr,
                                  header=cube_merge_high.wcs.celestial.to_header())
            hdu.writeto(hpath("pyspeckit_{0}{1}.fits".format(names[ii], jj)),
                        clobber=True)

    return maps

