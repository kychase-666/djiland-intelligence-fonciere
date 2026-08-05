"""
Découpage des grandes scènes satellite en tuiles 512x512.

Optimise le traitement CPU/GPU : chaque tuile tient en mémoire et peut être
traitée en parallèle (Dask), évitant de charger une scène entière d'un coup.
"""
from __future__ import annotations

from typing import Iterator

import numpy as np
from loguru import logger

from config import TILE_SIZE


def iter_tiles(array: np.ndarray, size: int = TILE_SIZE) -> Iterator[tuple]:
    """Itère sur les tuiles (size x size) d'un tableau 2D/3D.

    Yields:
        (row_off, col_off, tuile) — la dernière tuile de chaque bord peut être
        plus petite si la dimension n'est pas multiple de `size`.
    """
    h, w = array.shape[-2], array.shape[-1]
    for r in range(0, h, size):
        for c in range(0, w, size):
            tile = array[..., r:r + size, c:c + size]
            yield r, c, tile


def tile_count(array: np.ndarray, size: int = TILE_SIZE) -> int:
    """Nombre de tuiles générées pour un tableau donné."""
    h, w = array.shape[-2], array.shape[-1]
    n = int(np.ceil(h / size) * np.ceil(w / size))
    logger.info(f"[TILING] {n} tuiles de {size}x{size} prévues.")
    return n
