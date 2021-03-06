import sys
import yt
import spectral_cube
from spectral_cube import SpectralCube
import numpy as np
import pylab as pl
from astropy.utils.console import ProgressBar
import paths
import subprocess
from itertools import izip
import os

red = pl.mpl.colors.LinearSegmentedColormap('red',
                                            {'red':[(0,1,1),(1,1,1)],
                                             'green':[(0,0,0),(1,1,1)],
                                             'blue':[(0,0,0),(1,1,1)]})
green = pl.mpl.colors.LinearSegmentedColormap('green',
                                              {'red':[(0,0,0),(1,1,1)],
                                               'green':[(0,1,1),(1,1,1)],
                                               'blue':[(0,0,0),(1,1,1)]})
blue = pl.mpl.colors.LinearSegmentedColormap('blue', {'red':[(0,0,0),(1,1,1)],
                                                      'green':[(0,0,0),(1,1,1)],
                                                      'blue':[(0,1,1),(1,1,1)]})

if 'yt13co' not in locals():
    cube13co = spectral_cube.SpectralCube.read(paths.mpath('APEX_13CO_2014_merge.fits'))
    yt13co = cube13co.with_mask(cube13co>0.1).to_yt()

mask = cube13co>0.2

if 'cube_h2co303' not in locals():
    cube_sio = SpectralCube.read(paths.molpath('APEX_SiO_54_bl.fits'))
    # HACK:
    mask._wcs = cube_sio.wcs
    ytsio = cube_sio.with_mask(mask).to_yt()
    cube_h2co303 = SpectralCube.read(paths.molpath('APEX_H2CO_303_202_bl.fits'))
    mask._wcs = cube_h2co303.wcs
    yth2co303 = cube_h2co303.with_mask(mask).to_yt()
    cube_h2co321 = SpectralCube.read(paths.molpath('APEX_H2CO_321_220_bl.fits'))
    mask._wcs = cube_h2co321.wcs
    yth2co321 = cube_h2co321.with_mask(mask).to_yt()

    #temcube = SpectralCube.read(paths.dpath('H2CO_321220_to_303202_cube_bl_temperature.fits'))
    #mask._wcs = temcube.wcs
    #yttem = temcube.with_mask(mask).to_yt()

def isosurfaces(yt13co):
    yt13co.periodicity = (True,True,True)
    surface2k = yt13co.surface(yt13co.all_data(), 'flux', 2)
    surface2k.export_sketchfab(title='CMZ 13CO 2-1',
                             description='Monochrome 13CO 2K isosurface')
    surface4k = yt13co.surface(yt13co.all_data(), 'flux', 4)
    surface4k.export_sketchfab(title='CMZ 13CO 2-1',
                             description='Monochrome 13CO 4K isosurface')

def render_chem(yth2co321=yth2co321, yth2co303=yth2co303, ytsio=ytsio,
                outdir='yt_renders_chem3', size=512, scale=1100.,
                nframes=60,
                north_vector=[1,0,0],
                rot_vector=[1,0,0],
                movie=True, camera_angle=[-0.6, 0.4, 0.6]):

    if not os.path.exists(paths.mpath(outdir)):
        os.makedirs(paths.mpath(outdir))

    tf1 = yt.ColorTransferFunction([0.1,2], grey_opacity=True)
    #tf1.add_gaussian(0.1,0.05, [1,0,0,1])
    #tf1.map_to_colormap(0, 0.5, scale=1, colormap='Reds')
    tf1.add_gaussian(0.25, 0.01, [1,0,0,1])
    tf1.add_step(0.25,0.5,[1,0,0,1])
    #tf1.add_step(1,2,[1,1,1,1])
    tf1.map_to_colormap(0.5,2,scale=1,colormap=red)
    tf2 = yt.ColorTransferFunction([0.1,2], grey_opacity=True)
    #tf2.add_gaussian(0.1,0.05, [0,1,0,1])
    #tf2.map_to_colormap(0, 0.5, scale=1, colormap='Greens')
    tf2.add_gaussian(0.25, 0.01, [0,1,0,1])
    tf2.add_step(0.25,0.5,[0,1,0,1])
    tf2.map_to_colormap(0.5,2,scale=1,colormap=green)
    tf3 = yt.ColorTransferFunction([0.1,2], grey_opacity=True)
    #tf3.add_gaussian(0.1,0.05, [0,0,1,1])
    #tf3.map_to_colormap(0, 0.5, scale=1, colormap='Blues')
    tf3.add_gaussian(0.25, 0.01, [0,0,1,1])
    tf3.add_step(0.25,0.5,[0,0,1,1])
    tf3.map_to_colormap(0.5,2,scale=1,colormap=blue)

    center = yth2co303.dataset.domain_dimensions /2.
    camh2co303 = yth2co303.dataset.h.camera(center, camera_angle, scale, size, tf3,
                                    north_vector=north_vector, fields='flux')
    camh2co321 = yth2co321.dataset.h.camera(center, camera_angle, scale, size, tf2,
                                    north_vector=north_vector, fields='flux')
    camsio = ytsio.dataset.h.camera(center, camera_angle, scale, size, tf1,
                            north_vector=north_vector, fields='flux')

    imh2co303  = camh2co303.snapshot()
    imh2co321  = camh2co321.snapshot()
    imsio  = camsio.snapshot()
    
    pl.figure(1)
    pl.clf()
    pl.imshow(imh2co303+imh2co321+imsio)
    pl.figure(2)
    pl.clf()
    pl.imshow(imh2co303[:,:,:3]+imh2co321[:,:,:3]+imsio[:,:,:3])

    if movie:
        images_h2co303 = [imh2co303]
        images_h2co321 = [imh2co321]
        images_sio = [imsio]

        r1 = camh2co303.rotation(2 * np.pi, nframes, rot_vector=rot_vector)
        r2 = camh2co321.rotation(2 * np.pi, nframes, rot_vector=rot_vector)
        r3 = camsio.rotation(2 * np.pi, nframes, rot_vector=rot_vector)
        pb = ProgressBar(nframes * 3)
        for (ii,(imh2co303,imh2co321,imsio)) in enumerate(izip(r1, r2, r3)):
            images_h2co303.append(imh2co303)
            images_h2co321.append(imh2co321)
            images_sio.append(imsio)

            imh2co303=imh2co303.swapaxes(0,1)
            imh2co303.write_png(paths.mpath(os.path.join(outdir,"h2co303_%04i.png" % (ii))),
                                        rescale=False)
            pb.update(ii*3)
            imsio=imsio.swapaxes(0,1)
            imsio.write_png(paths.mpath(os.path.join(outdir,"sio_%04i.png" % (ii))),
                                        rescale=False)
            pb.update(ii*3+1)
            imh2co321=imh2co321.swapaxes(0,1)
            imh2co321.write_png(paths.mpath(os.path.join(outdir,"h2co321_%04i.png" % (ii))),
                                        rescale=False)
            pb.update(ii*3+2)

        pb.next()


        save_images([i1+i2+i3
                     for i1,i2,i3 in izip(images_h2co303, images_h2co321, images_sio)],
                     paths.mpath(outdir))

        make_movie(paths.mpath(outdir))

        return images_h2co303,images_h2co321,images_sio
    else:
        return imh2co303,imh2co321,imsio

def make_13co_faces(ytcube=yt13co, outdir='yt_renders_13CO',
                size=1024, scale=1200., nframes=180,
                movie=True,
                camera_angle=[0, 0, 1],
                north_vector = [1, 0, 0],
                rot_vector1=[1,0,0],
                rot_vector2=[0.5,0.5,0.0],
                rot_vector3=[0.0,0.5,0.5],
               ):

    tf = yt.ColorTransferFunction([0,30], grey_opacity=True)
    #tf.map_to_colormap(0.1,5,colormap='Reds')
    tf.add_gaussian(2, 1, [1.0, 0.8, 0.0, 1.0])
    tf.add_gaussian(3, 2, [1.0, 0.5, 0.0, 1.0])
    tf.add_gaussian(5, 3, [1.0, 0.0, 0.0, 1.0])
    tf.add_gaussian(10, 5, [1.0, 0.0, 0.0, 0.5])
    tf.map_to_colormap(10, 30, colormap=red, scale=1)


    center = ytcube.dataset.domain_dimensions /2.
    ims = []
    for camera_angle in ([1,0,0],[0,1,0],[0,0,1]):
        cam = ytcube.dataset.h.camera(center, camera_angle, scale, size, tf,
                          north_vector=north_vector, fields='flux')

        im  = cam.snapshot()
        ims.append(im)

    save_images(ims, 'render_13co_faceon_1024')




def render_13co(ytcube=yt13co, outdir='yt_renders_13CO',
                size=512, scale=1200., nframes=180,
                movie=True,
                camera_angle=[0, 0, 1],
                north_vector = [1, 0, 0],
                rot_vector1=[1,0,0],
                rot_vector2=[0.5,0.5,0.0],
                rot_vector3=[0.0,0.5,0.5],
               ):

    if not os.path.exists(paths.mpath(outdir)):
        os.makedirs(paths.mpath(outdir))

    tf = yt.ColorTransferFunction([0,30], grey_opacity=True)
    #tf.map_to_colormap(0.1,5,colormap='Reds')
    tf.add_gaussian(2, 1, [1.0, 0.8, 0.0, 1.0])
    tf.add_gaussian(3, 2, [1.0, 0.5, 0.0, 1.0])
    tf.add_gaussian(5, 3, [1.0, 0.0, 0.0, 1.0])
    tf.add_gaussian(10, 5, [1.0, 0.0, 0.0, 0.5])
    tf.map_to_colormap(10, 30, colormap=red, scale=1)


    center = ytcube.dataset.domain_dimensions /2.
    cam = ytcube.dataset.h.camera(center, camera_angle, scale, size, tf,
                      north_vector=north_vector, fields='flux')

    im  = cam.snapshot()

    #images = [im]

    if movie:
        pb = ProgressBar(nframes*2+30)
        for ii,im in enumerate(cam.rotation(2 * np.pi, nframes/3, rot_vector=rot_vector1)):
            #images.append(im)
            im.write_png(paths.mpath(os.path.join(outdir,"%04i.png" % (ii))),
                         rescale=False)
            pb.update(ii)
        for jj,im in enumerate(cam.rotation(2 * np.pi, nframes/3, rot_vector=rot_vector2)):
            #images.append(im)
            im.write_png(paths.mpath(os.path.join(outdir,"%04i.png" %
                                                  (ii+jj))), rescale=False)
            pb.update(ii+jj)
        for kk,im in enumerate(cam.rotation(2 * np.pi, nframes/3, rot_vector=rot_vector3)):
            #images.append(im)
            im.write_png(paths.mpath(os.path.join(outdir,"%04i.png" %
                                                  (ii+jj+kk))), rescale=False)
            pb.update(ii+jj+kk)

        TheBrick = ytcube.world2yt([0.253, 0.016, 35])
        for LL, snapshot in enumerate(cam.move_to(TheBrick, 15)):
            #images.append(snapshot)
            snapshot.write_png(paths.mpath(os.path.join(outdir,'%04i.png' %
                                                        (ii+jj+kk+LL))),
                               rescale=False)
            pb.update(ii+jj+kk+LL)
        for mm, snapshot in enumerate(cam.zoomin(5, 15)):
            #images.append(snapshot)
            snapshot.write_png(paths.mpath(os.path.join(outdir,'%04i.png' %
                                                        (ii+jj+kk+LL+mm))),
                               rescale=False)
            pb.update(ii+jj+kk+LL+mm)
        for nn,im in enumerate(cam.rotation(2*np.pi, nframes/3, rot_vector=rot_vector1)):
            #images.append(im)
            im.write_png(paths.mpath(os.path.join(outdir,"%04i.png" % (ii+jj+kk+LL+mm+nn))),
                         rescale=False)
            pb.update(ii+jj+kk+LL+mm+nn)
        for oo,im in enumerate(cam.rotation(2 * np.pi, nframes/3, rot_vector=rot_vector2)):
            #images.append(im)
            im.write_png(paths.mpath(os.path.join(outdir,"%04i.png" %
                                                  (ii+jj+kk+LL+mm+nn+oo))), rescale=False)
            pb.update(ii+jj+kk+LL+mm+nn+oo)
        for pp,im in enumerate(cam.rotation(2 * np.pi, nframes/3, rot_vector=rot_vector3)):
            #images.append(im)
            im.write_png(paths.mpath(os.path.join(outdir,"%04i.png" %
                                                  (ii+jj+kk+LL+mm+nn+oo+pp))), rescale=False)
            pb.update(ii+jj+kk+LL+mm+nn+oo+pp)

        #save_images(images, paths.mpath(outdir))

        pipe = make_movie(paths.mpath(outdir))
        
        return images
    else:
        return im

def save_images(images, prefix):
    """Save a sequence of images, at a common scaling
    Reduces flickering
    """
    if not os.path.exists(prefix):
        os.makedirs(prefix)
 
    cmax = max(np.percentile(i[:, :, :3].sum(axis=2), 99.5) for i in images)
    amax = max(np.percentile(i[:, :, 3], 95) for i in images)
    print cmax, amax
 
    for i, image in enumerate(images):
        image = image.rescale(cmax=cmax, amax=amax).swapaxes(0,1)
        image.write_png("%s/%04i.png" % (prefix, i), rescale=False)

def make_movie(moviepath, overwrite=True):
    """
    Use ffmpeg to generate a movie from the image series
    """

    outpath = os.path.join(moviepath,'out.mp4')

    if os.path.exists(outpath) and overwrite:
        command = ['ffmpeg', '-y', '-r','5','-i',
                   os.path.join(moviepath,'%04d.png'),
                   '-c:v','libx264','-r','30','-pix_fmt', 'yuv420p',
                   outpath]
    elif os.path.exists(outpath):
        log.info("File {0} exists - skipping".format(outpath))
    else:
        command = ['ffmpeg', '-r', '5', '-i',
                   os.path.join(moviepath,'%04d.png'),
                   '-c:v','libx264','-r','30','-pix_fmt', 'yuv420p',
                   outpath]

    pipe = subprocess.Popen(command, stdout=subprocess.PIPE, close_fds=True)

    pipe.wait()

    return pipe
