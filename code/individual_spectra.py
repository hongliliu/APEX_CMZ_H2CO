import pyregion
import pyspeckit
from paths import h2copath, mergepath, figurepath, regpath
import os
from pyspeckit_fitting import h2co_radex_fitter, simplemodel, simple_fitter


if 'cube' not in locals():
    cube = pyspeckit.Cube(os.path.join(mergepath, 'APEX_H2CO_merge_high.fits'))
    etamb = 0.75 # http://www.apex-telescope.org/telescope/efficiency/
    cube.cube /= etamb
    noise = fits.getdata(mergepath+'APEX_H2CO_merge_high_noise.fits') / etamb
    spectra = {}

cube.Registry.add_fitter('h2co_mm_radex', h2co_radex_fitter, 5,
                         multisingle='multi')
cube.Registry.add_fitter('h2co_simple', simple_fitter, 4, multisingle='multi')

#spectra = {
#        'brick1': cube.get_apspec((0.2426,0.0081,30), coordsys='galactic', wunit='arcsec'),
#        'brick2': cube.get_apspec((0.2583,0.0181,30), coordsys='galactic', wunit='arcsec'),
#        '20kms': cube.get_apspec((3.59977500e+02,  -6.25e-02, 30), coordsys='galactic', wunit='arcsec'),
#    }
#
#pars = {
#    'brick1': {'ncomp': 1},
#    'brick2': {'ncomp': 2},
#}


regs = pyregion.open(regpath+'spectral_apertures.reg')
with open(regpath+'spectral_ncomp.txt') as f:
    ncomps = eval(f.read())

for reg in regs:
    name = reg.attr[1]['text']
    if name not in spectra:
        sp = cube.get_apspec(reg.coord_list,coordsys='galactic',wunit='degree')
        sp.specname = reg.attr[1]['text']
        sp.error[:] = sp.stats((218e9,218.1e9))['std']
        spectra[name] = sp

    sp.plotter()

    ncomp = ncomps[sp.specname]
    spname = sp.specname.replace(" ","_")

    sp.specfit.Registry.add_fitter('h2co_mm_radex', h2co_radex_fitter, 5,
                             multisingle='multi')
    sp.specfit.Registry.add_fitter('h2co_simple', simple_fitter, 4, multisingle='multi')
    sp.specfit(fittype='h2co_simple', multifit=True,
               guesses=[1,25,5,0.5,1]*ncomp)

    sp.plotter()
    sp.specfit.plot_fit()
    sp.plotter.savefig(os.path.join(figurepath,
                                    "{0}_fit_4_lines_simple.pdf".format(spname)))

    sp.specfit(fittype='h2co_mm_radex', multifit=True,
               guesses=[100,14,4.5,
                        sp.specfit.parinfo['VELOCITY0'].value,
                        sp.specfit.parinfo['WIDTH0'].value]*ncomp,
               limits=[(20,200),(11,15),(3,5.5),(-105,105),(1,8)]*ncomp,
               limited=[(True,True)]*5*ncomp,
               fixed=[False,False,False,True,True]*ncomp,
               quiet=False,)
    sp.plotter.savefig(os.path.join(figurepath,
                                    "{0}_fit_h2co_mm_radex.pdf".format(spname)))


    individual_fits=False
    if individual_fits:
        flux = 3.6 # Jy
        col_per_jy = 2e22 # cm^-2
        dvdpc = 5.0 # km/s/pc
        logX = -8.3
        logcol = np.log10(flux*col_per_jy/dvdpc) + logX

        spectra['WarmSpot'].specfit(fittype='h2co_mm_radex', multifit=True,
                                    guesses=[100,logcol,4.5,35,3.0],
                                    limits=[(20,200),(11,15),(3,5.5),(-105,105),(1,5)],
                                    limited=[(True,True)]*5,
                                    fixed=[False,True,True,False,False],
                                    quiet=False,)

        spectra['WarmSpot'].specfit(fittype='h2co_mm_radex', multifit=True,
                                    guesses=[100,logcol+np.log10(2/3.),4.5,27,3.0]+[100,logcol+np.log10(1.0/3.),4.5,53,3.0],
                                    limits=[(20,200),(11,15),(3,5.5),(-105,105),(1,8)]+[(20,200),(11,15),(3,5.5),(-105,105),(1,6)],
                                    limited=[(True,True)]*10,
                                    fixed=[False,True,True,False,False]*2,
                                    quiet=False,)

        flux = 5.0
        logX = -8.5
        logcol = np.log10(flux*col_per_jy/dvdpc / 2.) + logX

        spectra['Brick SW'].specfit(fittype='h2co_mm_radex', multifit=True,
                                    guesses=[133,12.94,5.977,37.17,9.88],
                                    limits=[(20,200),(11,15),(3,6.5),(-105,105),(1,15)],
                                    limited=[(True,True)]*5,
                                    #fixed=[False,False,True,False,False],
                                    fixed=[False,True,True,False,False])

        spectra['50kmsColdExtension'].specfit(fittype='h2co_mm_radex', multifit=True,
                                    guesses=[33,12.94,4.0,24.4,7],
                                    limits=[(20,200),(11,15),(3,6.5),(-105,105),(1,15)],
                                    limited=[(True,True)]*5,
                                    #fixed=[False,False,True,False,False],
                                    fixed=[False,False,True,False,False])

        #spectra['Sgr B2 SW'].specfit(fittype='h2co_mm_radex', multifit=True,
        #                            guesses=[125,14.14,4.0,47.72,5.66]+[125,14.14,4.0,55.72,5.66],
        #                            limits=[(20,200),(11,15),(3,6.5),(-105,105),(1,15)]*2,
        #                            limited=[(True,True)]*5*2,
        #                            #fixed=[False,False,True,False,False],
        #                            fixed=[False,False,True,True,True]+[False,False,True,False,False])



    dopymc = False
    if dopymc:
        import agpy

        sp = spectra['20 kms']
        # SHOULD BE 
        spmc = sp.specfit.get_pymc(use_fitted_values=True, db='hdf5', dbname='h2co_mm_fit_20kmsCld.hdf5')
        #spmc = sp.specfit.fitter.get_pymc(sp.xarr, sp.data, sp.error,
        #                                  use_fitted_values=True, db='hdf5',
        #                                  dbname='h2co_mm_fit_20kmsCld.hdf5')
        spmc.sample(100000)
        agpy.pymc_plotting.hist2d(spmc, 'TEMPERATURE0', 'DENSITY0', doerrellipse=False, clear=True, bins=50, fignum=4)
        agpy.pymc_plotting.hist2d(spmc, 'TEMPERATURE0', 'COLUMN0', doerrellipse=False, clear=True, bins=50,fignum=5)
        agpy.pymc_plotting.hist2d(spmc, 'DENSITY0', 'COLUMN0', doerrellipse=False, clear=True, bins=50,fignum=6)


        pars = dict([(k,spmc.trace(k)[-50:]) for k in sp.specfit.parinfo.keys()])
        sp.plotter.autorefresh=False
        for ii in xrange(0,50):
            sp.specfit.plot_model([pars[k][ii] for k in sp.specfit.parinfo.keys()],
                                  clear=False,
                                  composite_fit_color='r',
                                  plotkwargs={'alpha':0.01})

        sp.plotter.refresh()
