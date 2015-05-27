raise Exception("Use h2co_modeling.constrain_parameters instead")
"""
Functions for fitting temperature (and density and column) from the line ratio
plus whatever other constraints are available
"""
import inspect
import time

import numpy as np
from scipy.ndimage.interpolation import map_coordinates
from astropy import units as u
from astropy import log
import pylab as pl

from h2co_modeling import grid_fitter
from paraH2COmodel import generic_paraH2COmodel

short_mapping = {'dens': 'density',
                 'col': 'column',
                 'tem': 'temperature'}

class paraH2COmodel(generic_paraH2COmodel):

    def __init__(self, tbackground=2.73, gridsize=[250.,101.,100.]):
        t0 = time.time()
        from pyspeckit_fitting import (texgrid303, taugrid303, texgrid321, taugrid321,
                                       texgrid322, taugrid322, hdr)
        t1 = time.time()
        log.debug("Loading grids took {0:0.1f} seconds".format(t1-t0))

        self.texgrid303 = texgrid303
        self.taugrid303 = taugrid303
        self.texgrid321 = texgrid321
        self.taugrid321 = taugrid321
        self.texgrid322 = texgrid322
        self.taugrid322 = taugrid322
        self.hdr = hdr

        self.Tbackground = tbackground
        self.tline303a = ((1.0-np.exp(-np.array(self.taugrid303))) *
                          (self.texgrid303-self.Tbackground))
        self.tline321a = ((1.0-np.exp(-np.array(self.taugrid321))) *
                          (self.texgrid321-self.Tbackground))
        self.tline322a = ((1.0-np.exp(-np.array(self.taugrid322))) *
                          (self.texgrid322-self.Tbackground))

        zinds,yinds,xinds = np.indices(self.tline303a.shape)
        upsample_factor = np.array([gridsize[0]/self.tline303a.shape[0], # temperature
                                    gridsize[1]/self.tline303a.shape[1], # density
                                    gridsize[2]/self.tline303a.shape[2]], # column
                                   dtype='float')
        uzinds,uyinds,uxinds = upsinds = np.indices([x*us
                                                     for x,us in zip(self.tline303a.shape,
                                                                     upsample_factor)],
                                                   dtype='float')
        self.tline303 = map_coordinates(self.tline303a,
                                   upsinds/upsample_factor[:,None,None,None],
                                   mode='nearest')
        self.tline321 = map_coordinates(self.tline321a,
                                   upsinds/upsample_factor[:,None,None,None],
                                   mode='nearest')
        self.tline322 = map_coordinates(self.tline322a,
                                   upsinds/upsample_factor[:,None,None,None],
                                   mode='nearest')
    
        self.tline = {303: self.tline303,
                      321: self.tline321,
                      322: self.tline322}

        assert self.hdr['CTYPE2'].strip() == 'LOG-DENS'
        assert self.hdr['CTYPE1'].strip() == 'LOG-COLU'

        self.columnarr = ((uxinds + self.hdr['CRPIX1']-1)*self.hdr['CDELT1'] /
                      float(upsample_factor[2])+self.hdr['CRVAL1']) # log column
        self.densityarr  = ((uyinds + self.hdr['CRPIX2']-1)*self.hdr['CDELT2'] /
                      float(upsample_factor[1])+self.hdr['CRVAL2']) # log density
        self.temparr    = ((uzinds + self.hdr['CRPIX3']-1)*self.hdr['CDELT3'] /
                      float(upsample_factor[0])+self.hdr['CRVAL3']) # lin temperature
        self.drange = [self.densityarr.min(), self.densityarr.max()]
        self.crange = [self.columnarr.min(),  self.columnarr.max()]
        self.trange = [self.temparr.min(),    self.temparr.max()]
        self.darr = self.densityarr[0,:,0]
        self.carr = self.columnarr[0,0,:]
        self.tarr = self.temparr[:,0,0]
        self.axes = {'dens': self.darr,
                     'col': self.carr,
                     'tem': self.tarr}
        self.labels = {'dens': 'Density $n(\mathrm{H}_2)$ [log cm$^{-3}$]',
                       'col': 'p-H$_2$CO [log cm$^{-2}$/(km s$^{-1}$ pc)]',
                       'tem': 'Temperature (K)'}

        # While the individual lines are subject to filling factor uncertainties, the
        # ratio is not.
        self.modelratio1 = self.tline321/self.tline303
        self.modelratio2 = self.tline322/self.tline321

        self.model_logabundance = np.log10(10**self.columnarr / u.pc.to(u.cm) /
                                           10**self.densityarr)

        t2 = time.time()
        log.debug("Grid initialization took {0:0.1f} seconds total,"
                  " {1:0.1f} since loading grids.".format(t2-t0,t2-t1))

    def list_parameters():
        return ['taline303',  'etaline303', 'taline321',  'etaline321',
                'taline322',  'etaline322', 'logabundance',  'elogabundance',
                'logh2column',  'elogh2column', 'ratio321303',  'eratio321303',
                'ratio321322',  'eratio321322', 'linewidth']

    def set_constraints_fromrow(self, row, **kwargs):

        mapping = {'e321':'etaline321',
                   'Smean321':'taline321',
                   'Smean303':'taline303',
                   'er321303':'eratio321303',
                   'eratio321303':'eratio321303',
                   'e303':'etaline303',
                   'r321303':'ratio321303',
                   'ratio321303':'ratio321303',
                   'r321303':'ratio321303',
                   'er321303':'eratio321303',
                   'logabundance':'logabundance',
                   'elogabundance':'elogabundance',
                   'logh2column':'logh2column',
                   'elogh2column':'elogh2column',
                   'dustmindens':'linmindens',
                   'v_rms':'linewidth',
                  }
        pars = {mapping[k]: row[k] for k in row.colnames if k in mapping}
        pars.update(**kwargs)

        self.set_constraints(**pars)

    def set_constraints(self,
                        taline303=None, etaline303=None,
                        taline321=None, etaline321=None,
                        taline322=None, etaline322=None,
                        logabundance=None, elogabundance=None,
                        logh2column=None, elogh2column=None,
                        ratio321303=None, eratio321303=None,
                        ratio321322=None, eratio321322=None,
                        linmindens=None,
                        mindens=None, emindens=0.2,
                        linewidth=None):

        argspec=inspect.getargvalues(inspect.currentframe())
        for arg in argspec.args:
            if argspec.locals[arg] is not None:
                setattr(self, arg, argspec.locals[arg])

        self.chi2_X = (self.chi2_abundance(logabundance, elogabundance) 
                       if not any(arg is None for arg in (logabundance,
                                                          elogabundance))
                       else 0)

        self.chi2_h2 = (self.chi2_column(logh2column, elogh2column,
                                         logabundance, linewidth) 
                        if not
                        any(arg is None for arg in (logabundance, logh2column,
                                                      elogh2column, linewidth))
                        else 0)

        self.chi2_ff1 = (self.chi2_fillingfactor(taline303, etaline303, 303)
                         if not any(arg is None for arg in (taline303,
                                                            etaline303))
                         else 0)


        self.chi2_ff2 = (self.chi2_fillingfactor(taline321, etaline321, 321)
                         if not any(arg is None for arg in (taline321,
                                                            etaline321))
                         else 0)

        self.chi2_r321303 = (self.grid_getmatch_321to303(ratio321303,
                                                         eratio321303)
                             if not any(arg is None for arg in (ratio321303,
                                                                eratio321303))
                             else 0)
        if np.all(~np.isfinite(self.chi2_r321303)):
            self.chi2_r321303 = 0

        self.chi2_r321322 = (self.grid_getmatch_321to303(ratio321322,
                                                         eratio321322)
                             if not any(arg is None for arg in (ratio321322,
                                                                eratio321322))
                             else 0)
        if np.all(~np.isfinite(self.chi2_r321322)):
            self.chi2_r321322 = 0

        if linmindens is not None:
            if mindens is not None:
                raise ValueError("Both linmindens and logmindens were set.")
            mindens = np.log10(linmindens)

        if mindens is not None:
            self.chi2_dens = (((self.densityarr - mindens)/emindens)**2
                              * (self.densityarr < (mindens-emindens)))
        else:
            self.chi2_dens = 0

        self.compute_chi2_fromcomponents()

    def compute_chi2_fromcomponents(self):
        """
        Compute the total chi2 from the individual chi2 components
        """
        self.chi2 = (self.chi2_X + self.chi2_h2 + self.chi2_ff1 + self.chi2_ff2
                     + self.chi2_r321322 + self.chi2_r321303 + self.chi2_dens)


    def parplot(self, par1='col', par2='dens', nlevs=5, levels=None):

        xax = self.axes[par1]
        yax = self.axes[par2]
        xlabel = self.labels[par1]
        ylabel = self.labels[par2]
        axis = {('col','dens'): 0,
                ('dens','tem'): 2,
                ('col','tem'): 1}[(par1,par2)]

        if levels is None:
            levels = np.arange(nlevs)

        xmaxlike = self.parconstraints['{0}_chi2'.format(short_mapping[par1])]
        ymaxlike = self.parconstraints['{0}_chi2'.format(short_mapping[par2])]
        xexpect = self.parconstraints['E({0})'.format(short_mapping[par1])]
        yexpect = self.parconstraints['E({0})'.format(short_mapping[par2])]

        fig = pl.gcf()
        fig.clf()
        ax1 = pl.subplot(2,2,1)
        pl.contourf(xax, yax, self.chi2_r321303.min(axis=axis),
                    levels=self.chi2_r321303.min()+levels, alpha=0.5)
        pl.contour(xax, yax, self.chi2.min(axis=axis),
                   levels=self.chi2.min()+levels)
        pl.plot(xmaxlike, ymaxlike, 'o', facecolor='none', edgecolor='k')
        pl.plot(xexpect, yexpect, 'x', facecolor='none', edgecolor='k')
        if self.chi2_r321322:
            pl.contour(xax, yax, self.chi2_r321322.min(axis=axis),
                       levels=self.chi2_r321322.min()+levels,
                       cmap=pl.cm.bone)
        pl.title("Ratio $3_{0,3}-2_{0,2}/3_{2,1}-2_{2,0}$")

        ax4 = pl.subplot(2,2,2)
        if hasattr(self.chi2_X, 'size'):
            pl.contourf(xax, yax, self.chi2_X.min(axis=axis),
                        levels=self.chi2_X.min()+levels, alpha=0.5)
        pl.contour(xax, yax, self.chi2.min(axis=axis),
                   levels=self.chi2.min()+levels)
        pl.plot(xmaxlike, ymaxlike, 'o', facecolor='none', edgecolor='k')
        pl.plot(xexpect, yexpect, 'x', facecolor='none', edgecolor='k')
        pl.title("log(p-H$_2$CO/H$_2$) "
                 "$= {0:0.1f}\pm{1:0.1f}$".format(self.logabundance,
                                                  self.elogabundance))

        ax3 = pl.subplot(2,2,3)
        if hasattr(self.chi2_h2, 'size'):
            pl.contourf(xax, yax, self.chi2_h2.min(axis=axis),
                        levels=self.chi2_h2.min()+levels, alpha=0.5)
        pl.contour(xax, yax, self.chi2.min(axis=axis),
                   levels=self.chi2.min()+levels)
        pl.plot(xmaxlike, ymaxlike, 'o', facecolor='none', edgecolor='k')
        pl.plot(xexpect, yexpect, 'x', facecolor='none', edgecolor='k')
        pl.title("Total log$(N(\\mathrm{{H}}_2))$ ")
        #         "= {0:0.1f}\pm{1:0.1f}$".format(self.logh2column,
        #                                         self.elogh2column))
        ax5 = pl.subplot(2,2,4)
        #if hasattr(self.chi2_ff1, 'size'):
        #    pl.contourf(xax, yax, (self.chi2_ff1.min(axis=axis)),
        #                levels=self.chi2_ff1.min()+levels, alpha=0.5)
        if hasattr(self.chi2_dens, 'size'):
            pl.contourf(xax, yax, (self.chi2_dens.min(axis=axis)),
                        levels=self.chi2_dens.min()+levels, alpha=0.5)
        pl.contour(xax, yax, self.chi2.min(axis=axis),
                   levels=self.chi2.min()+levels)
        if hasattr(self, 'taline303'):
            pl.contour(xax, yax, (self.tline303 < 10*self.taline303).max(axis=axis),
                       levels=[0.5], colors='k')
        pl.plot(xmaxlike, ymaxlike, 'o', facecolor='none', edgecolor='k')
        pl.plot(xexpect, yexpect, 'x', facecolor='none', edgecolor='k')
        #pl.contour(xax, yax, (tline303 < 100*par1).max(axis=axis), levels=[0.5], colors='k')
        #pl.contour(xax, yax, (tline321 < 10*par2).max(axis=axis), levels=[0.5], colors='k', linestyles='--')
        #pl.contour(xax, yax, (tline321 < 100*par2).max(axis=axis), levels=[0.5], colors='k', linestyles='--')
        #pl.title("Line Brightness + $ff\leq1$")
        pl.title("Minimum Density")
        fig.text(0.05, 0.5, ylabel, horizontalalignment='center',
                verticalalignment='center',
                rotation='vertical', transform=fig.transFigure)
        fig.text(0.5, 0.02, xlabel, horizontalalignment='center', transform=fig.transFigure)


        if par1 == 'col':
            for ss in range(1,5):
                ax = pl.subplot(2,2,ss)
                ax.xaxis.set_ticks(np.arange(self.carr.min(), self.carr.max()))

        pl.subplots_adjust(wspace=0.25, hspace=0.45)
