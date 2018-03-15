import numpy as np

AVAILABLE_STRATEGIES = ['sum', 'mean', 'farthest', 'most_frequent',
                        'contrastive_mean']
__all__ = AVAILABLE_STRATEGIES


def sum(labels, distances, multi_class=True, t=0.0):
    if multi_class:
        return np.asarray([np.argmax(d.sum(axis=-2), axis=-1) for d in distances])

    return np.asarray([(d.sum(axis=-1) > t) for d in distances], dtype=int)


def mean(labels, distances, multi_class=True, t=0.0):
    if multi_class:
        return np.asarray([np.argmax(d.mean(axis=-2), axis=-1) for d in distances])

    return np.asarray([(d.mean(axis=-1) > t) for d in distances], dtype=int)


def contrastive_mean(labels, distances, multi_class=True, t=0.0):
    return (distances.mean(axis=-1) <= t).astype(np.int)


def farthest(labels, distances, multi_class=True, t=0.0):
    if multi_class:
        return np.asarray([np.argmax(d.max(axis=-2), axis=-1) for d in distances])

    return np.asarray([d[np.argmax(np.abs(d), axis=-1)] > t for d in distances], dtype=int)


def most_frequent(labels, distances, multi_class=True, t=0.0):
    return np.asarray([np.argmax(np.bincount(patch_labels)) for patch_labels in labels])
