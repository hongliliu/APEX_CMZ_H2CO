from astropy import table
import numpy as np

def flag_dendro(dend, catalog=None, smooth=False):
    """
    Remove / flag as "bad" objects in the dendrogram that are not H2CO
    """

    pixels_with_bad = [(518,122,142),
                       (508,123,10),
                       (533,124,48),
                       (857,103,126),
                       (904,102,105),
                       (884,95,118),
                       (515, 108, 1),
                      ]
    if catalog is not None:
        catalog.add_column(table.Column(name='IsNotH2CO', dtype=bool,
                                        data=np.zeros(len(catalog),
                                                      dtype='bool')))
    for obj in dend:
        obj.bad = False

    for x,y,z in pixels_with_bad:
        bad_obj = dend.structure_at([z/(2 if smooth else 1),y,x])
        if bad_obj:
            bad_obj = bad_obj.ancestor
            bad_obj.bad = True
            if catalog is not None:
                catalog[bad_obj.idx]['IsNotH2CO'] = True
            for obj in bad_obj.descendants:
                obj.bad = True
                catalog[obj.idx]['IsNotH2CO'] = True
        else:
            # sometimes these don't get IDd?
            pass
