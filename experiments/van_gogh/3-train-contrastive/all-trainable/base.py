import math

import numpy as np
from sklearn import metrics

from connoisseur import fusion
from connoisseur.fusion import ContrastiveFusion


def combine_pairs_for_training_gen(X, y, names, batch_size=32,
                                   anchor_painter_label=1):
    indices = [np.where(y == i)[0] for i in np.unique(y)]
    samples1 = indices[anchor_painter_label]
    indices.pop(anchor_painter_label)
    samples0 = np.concatenate(indices)
    np.random.shuffle(samples0)

    while True:
        c0 = np.hstack((
            np.random.choice(samples1, size=(math.floor(batch_size / 2), 1)),
            np.random.choice(samples0, size=(math.floor(batch_size / 2), 1))))
        c1 = np.random.choice(samples1, size=(math.ceil(batch_size / 2), 2))
        c = np.vstack((c0, c1))

        X_pairs = X[c.T]

        y_pairs = np.concatenate((np.zeros(c0.shape[0]),
                                  np.ones(c1.shape[1])))

        yield list(X_pairs), y_pairs


def combine_pairs_for_evaluation(X_base, y_base,
                                 X_eval, y_eval,
                                 anchor_painter_label=1, patches_used=40):
    # Filter some artist paintings (0:nvg, 1:vg) and flat out paintings,
    # leaving a list of patches.
    s = y_base == anchor_painter_label
    X_base = X_base[s]
    X_base = np.concatenate(X_base)

    # Aggregate test patches by their respective paintings.
    _X, _y, _names = [], [], []

    X_pairs = [[x_eval_patches[
                    np.random.choice(x_eval_patches.shape[0], patches_used)],
                X_base[np.random.choice(X_base.shape[0], patches_used)]]
               for x_eval_patches in X_eval]
    y_pairs = (y_eval == anchor_painter_label).astype(np.int)
    return X_pairs, y_pairs


def evaluate(model, data, batch_size):
    print('evaluating model with patch fusion strategies')

    X_train, y_train = data['train']
    X_test, y_test = data['test']
    X, y = combine_pairs_for_evaluation(X_train, y_train,
                                        X_test, y_test,
                                        anchor_painter_label=1,
                                        patches_used=40)
    scores = {'test': -1}
    for threshold in (.2, .3, .5):
        for strategy in ('contrastive_avg', 'most_frequent'):
            f = ContrastiveFusion(model, strategy=strategy)
            p = f.predict(X, batch_size=batch_size, threshold=threshold)
            accuracy_score = metrics.accuracy_score(y, p)
            print('score using', strategy,
                  'strategy, threshold %.1f: %.2f%%'
                  % (threshold, 100 * accuracy_score),
                  '\nConfusion matrix:\n', metrics.confusion_matrix(y, p),
                  # '\nWrong predictions: %s' % names[y != p]
                  )

            if accuracy_score > scores['test']:
                scores['test'] = accuracy_score
    return scores