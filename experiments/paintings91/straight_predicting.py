"""Paintings91 Connoisseur Straight Predicting.

Uses VGG to transform paintings in Paintings91 dataset into their
low-dimensional representations and, finally, exploits LinearSVM to classify
these paintings.

Author: Lucas David -- <ld492@drexel.edu>
Licence: MIT License 2016 (c)

"""
import abc
import logging
import os
from datetime import datetime

import numpy as np
import tensorflow as tf
from connoisseur import Connoisseur, datasets, utils
from keras.applications import VGG19
from keras.engine import Input
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.svm import SVC


class Paintings91(Connoisseur, metaclass=abc.ABCMeta):
    def build(self):
        consts = self.constants
        images = Input(batch_shape=[consts.batch_size] + consts.image_shape)
        return VGG19(weights='imagenet', include_top=False,
                     input_tensor=images)

    def data(self, phase='training'):
        consts = self.constants

        with tf.device('/cpu'):
            dataset = datasets.Paintings91(consts.data_dir).check()
            data_generator = dataset.as_keras_generator()

            return data_generator.flow_from_directory(
                os.path.join(consts.data_dir, 'Images'),
                target_size=consts.image_shape[:2],
                classes=consts.classes,
                batch_size=consts.batch_size,
                seed=consts.seed)


def main(constants_file='./constants.json'):
    consts = utils.Constants(constants_file).load()

    tf.logging.set_verbosity(tf.logging.INFO)
    logging.basicConfig(level=logging.INFO,
                        filename=os.path.join(consts.logging_dir,
                                              str(datetime.now()) + '.log'))

    c = Paintings91(constants=consts)

    try:
        t = utils.Timer()
        data = c.data()
        X, y = [], []

        tf.logging.info('entering feature extraction phase')

        with tf.device(consts.device):
            # Transform images into their low-dimensional representations.
            model = c.build()

            for i in range(consts.n_iterations):
                _X, _y = next(data)
                X += [
                    model.predict_on_batch(_X).reshape((consts.batch_size, -1))]
                y += [np.argmax(_y, axis=1)]

        # Separate data between training and testing.
        X, y = np.concatenate(X), np.concatenate(y)

        tf.logging.info('feature extraction completed -- dataset shape: %s',
                        X.shape)
        tf.logging.info('entering SVM classifier training phase')

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=.20,
                                                            random_state=consts.seed)
        params = [
            {'C': [1, 10, 100, 1000], 'kernel': ['linear']},
            {'C': [1, 10, 100, 1000], 'gamma': [0.001, 0.0001],
             'kernel': ['rbf']},
        ]

        grid = GridSearchCV(SVC(), params, cv=None, n_jobs=-1)
        grid.fit(X_train, y_train)

        tf.logging.info('training complete')

        tf.logging.info('best training score: %.2f%%', grid.best_score_)
        tf.logging.info('test score: %.2f%%', grid.score(X_test, y_test))
        tf.logging.info('experiment completed (%s)' % t)

    except KeyboardInterrupt:
        tf.logging.warning('interrupted by the user')


if __name__ == '__main__':
    print(__doc__, flush=True)
    main()
