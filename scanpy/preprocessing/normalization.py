import numpy as np
from scipy.sparse import issparse
from sklearn.utils import sparsefuncs
from .. import logging as logg

def _normalize_data(X, counts, after=None, cell_subset=None, copy=False):
    X = X.copy() if copy else X
    if after is None:
        after = np.median(counts[cell_subset]) if cell_subset is not None else np.median(counts)
    if cell_subset is None:
        counts /= after
    else:
        counts[np.logical_not(cell_subset)] = 1
        counts[cell_subset] = counts[cell_subset]/after
    counts += (counts == 0)
    if issparse(X):
        X = sparsefuncs.inplace_row_scale(X, 1/counts)
    else:
        X /= counts[:, None]
    return X if copy else None

def normalize_quantile(data, cell_sum_after=None, quantile=1, min_counts=1, key_n_counts=None,
                       inplace=True, layers=[], layer_norm=None):
    """Normalize total counts per cell.

    Normalize each cell by total counts over genes, so that every cell has
    the same total count after normalization.

    Similar functions are used, for example, by Seurat [Satija15]_, Cell Ranger
    [Zheng17]_ or SPRING [Weinreb17]_.

    Parameters
    ----------
    data : :class:`~anndata.AnnData`
        The annotated data matrix of shape `n_obs` × `n_vars`. Rows correspond
        to cells and columns to genes.
    cell_sum_after : `float` or `None`, optional (default: `None`)
        If `None`, after normalization, each cell has a total count equal
        to the median of the *counts_per_cell* before normalization.
    quantile : `float`, optional (default: 1)
        Only use genes are less than fraction (specified by *quantile*)
        of the total reads in every cell.
    min_counts : `int`, optional (default: 1)
        Cells with counts less than `min_counts` are filtered out during
        normalization.
    key_n_counts : `str`, optional (default: `None`)
        Name of the field in `adata.obs` where the total counts per cell are
        stored.
    inplace : `bool`, optional (default: `True`)
        Whether to change data.X and data.layers or just return
        dictionary with normalized copies of data.X and data.layers.
    layers : `str` or list of `str`, optional (default: `[]`)
        List of layers to normalize. Set to `'all'` to normalize all layers.
    layer_norm : `str` or `None`, optional (default: `None`)
        Specifies how to normalize layers.
        If `None`, after normalization, for each layer in *layers* each cell
        has a total count equal to the median of the *counts_per_cell* before
        normalization of the layer.
        If `'after'`, for each layer in *layers* each cell has
        a total count equal to cell_sum_after.
        If `'X'`, for each layer in *layers* each cell has a total count equal
        to the median of the *counts_per_cell* of data.X before normalization.

    Returns
    -------
    Returns or updates `adata` with normalized version of the original
    `adata.X`, depending on `copy`.

    Examples
    --------
    >>> adata = AnnData(np.array([[1, 0, 1], [3, 0, 1], [5, 6, 1]]))
    >>> sc.pp.normalize_quantile(adata, quantile=0.7)
    >>> print(adata.X)
    [[1.         0.         1.        ]
     [3.         0.         1.        ]
     [0.71428573 0.85714287 0.14285715]]
    """
    if quantile < 0 or quantile > 1:
        raise ValueError('Choose quantile between 0 and 1.')

    X = data.X
    gene_subset = None
    if not inplace:
    # not recarray because need to support sparse
        dat = {}

    if quantile < 1:
        logg.msg('normalizing by count per cell for \
                  genes that make up less than quantile * total count per cell', r=True)
        X = data.X

        counts_per_cell = X.sum(1)
        counts_per_cell = np.ravel(counts_per_cell)

        gene_subset = (X>counts_per_cell[:, None]*quantile).sum(0)
        gene_subset = (np.ravel(gene_subset) == 0)
    else:
        logg.msg('normalizing by total count per cell', r=True)

    X = X if gene_subset is None else data[:, gene_subset].X
    counts_per_cell = X.sum(1)
    #get rid of data view
    counts_per_cell = np.ravel(counts_per_cell).copy()
    del X
    del gene_subset

    if key_n_counts is not None:
        adata.obs[key_n_counts] = counts_per_cell
    cell_subset = counts_per_cell >= min_counts

    if layer_norm == 'after':
        after = cell_sum_after
    elif layer_norm == 'X':
        after = np.median(counts_per_cell[cell_subset])
    elif layer_norm is None:
        after = None
    else: raise ValueError('layer_norm should be "after", "X" or None')

    if inplace:
        _normalize_data(data.X, counts_per_cell, cell_sum_after, cell_subset)
    else:
        dat['X'] = _normalize_data(data.X, counts_per_cell, cell_sum_after, cell_subset, True)

    layers = data.layers.keys() if layers == 'all' else layers
    for layer in layers:
        L = data.layers[layer]
        counts = np.ravel(L.sum(1))
        if inplace:
            _normalize_data(L, counts, after)
        else:
            dat[layer] = _normalize_data(L, counts, after, copy=True)

    logg.msg('    finished', t=True, end=': ')
    logg.msg('normalized adata.X')
    if key_n_counts is not None:
        logg.msg('and added \'{}\', counts per cell before normalization (adata.obs)'
            .format(key_n_counts))

    return dat if not inplace else None

def normalize_total(data, cell_sum_after=None, counts_per_cell=None, key_n_counts=None,
                    inplace=True, layers=[], layer_norm=None, min_counts=1):
    """Normalize total counts per cell.

    Normalize each cell by total counts over all genes, so that every cell has
    the same total count after normalization.

    Similar functions are used, for example, by Seurat [Satija15]_, Cell Ranger
    [Zheng17]_ or SPRING [Weinreb17]_.

    Parameters
    ----------
    data : :class:`~anndata.AnnData`
        The annotated data matrix of shape `n_obs` × `n_vars`. Rows correspond
        to cells and columns to genes.
    cell_sum_after : `float` or `None`, optional (default: `None`)
        If `None`, after normalization, each cell has a total count equal
        to the median of the *counts_per_cell* before normalization.
    counts_per_cell : `np.array`, optional (default: `None`)
        Precomputed counts per cell.
    key_n_counts : `str`, optional (default: `'n_counts'`)
        Name of the field in `adata.obs` where the total counts per cell are
        stored.
    copy : `bool`, optional (default: `False`)
        If an :class:`~anndata.AnnData` is passed, determines whether a copy
        is returned.
    layers : `str` or list of `str`, optional (default: `[]`)
        List of layers to normalize. Set to `'all'` to normalize all layers.
    layer_norm : `str` or `None`, optional (default: `None`)
        Specifies how to normalize layers.
        If `None`, after normalization, for each layer in *layers* each cell has a total count equal
        to the median of the *counts_per_cell* before normalization of the layer.
        If `'after'`, for each layer in *layers* each cell has a total count equal
        to cell_sum_after.
        If `'X'`, for each layer in *layers* each cell has a total count equal
        to the median of the *counts_per_cell* of data.X before normalization.
    min_counts : `int`, optional (default: 1)
        Cells with counts less than `min_counts` are filtered out during
        normalization.

    Returns
    -------
    Returns or updates `adata` with normalized version of the original
    `adata.X`, depending on `copy`.

    Examples
    --------
    >>> adata = AnnData(np.array([[1, 0], [3, 0], [5, 6]]))
    >>> print(adata.X.sum(axis=1))
    [  1.   3.  11.]
    >>> sc.pp.normalize_total(adata)
    >>> print(adata.obs)
    >>> print(adata.X.sum(axis=1))
       n_counts
    0       1.0
    1       3.0
    2      11.0
    [ 3.  3.  3.]
    >>> sc.pp.normalize_total(adata, cell_sum_after=1,
    >>>                       key_n_counts='n_counts2')
    >>> print(adata.obs)
    >>> print(adata.X.sum(axis=1))
       n_counts  n_counts2
    0       1.0        3.0
    1       3.0        3.0
    2      11.0        3.0
    [ 1.  1.  1.]
    """
    return normalize_quantile(data=data, cell_sum_after=cell_sum_after,
                              key_n_counts=key_n_counts, inplace=inplace, layers=layers,
                              layer_norm=layer_norm, min_counts=min_counts, quantile=1)