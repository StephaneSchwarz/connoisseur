"""Paintings91 Connoisseur Training.


Author: Lucas David -- <ld492@drexel.edu>
Licence: MIT License 2016 (c)

"""
import json
import logging
import os

import tensorflow as tf

import connoisseur as conn

N_EPOCHS = 1000000

config = tf.ConfigProto(allow_soft_placement=True)

connoisseur_params = dict(
    n_epochs=N_EPOCHS, learning_rate=.001, dropout=.5,
    checkpoint_every=100,
    session_config=config)

data_set_params = dict(
    n_threads=1,
    train_validation_test_split=[.8, .2],
    save_in='./data/',
    batch_size=10,
    n_epochs=N_EPOCHS)


def main():
    os.makedirs(os.path.join(conn.settings.BASE_DIR, 'paintings91', 'logs'), exist_ok=True)
    logging.basicConfig(
        filename=os.path.join(conn.settings.BASE_DIR, 'paintings91', 'logs', 'training.log'),
        level=logging.DEBUG)

    logger = logging.getLogger('connoisseur')

    t = conn.utils.Timer()

    model = conn.connoisseurs.Paintings91(**connoisseur_params)
    dataset = conn.datasets.Paintings91(**data_set_params)

    logger.info('Executing with the following parameters:\n%s',
                json.dumps(dataset.parameters, indent=2))
    try:
        with tf.device('/gpu:1'):
            logger.info('fetching data set...')
            images, labels = dataset.load().preprocess().as_batches()

            logger.info('training...')
            model.fit(images, labels, validation=dataset.as_batches(phase='validation'))

            test_score = model.score(*dataset.as_batches('test'))
            logger.info('score on test dataset: %.2f%%', (100 * test_score))

    except KeyboardInterrupt:
        logger.info('interrupted by user (%s)', t)
    else:
        logger.info('finished (%s)', t)

    print('bye')


if __name__ == '__main__':
    print(__doc__, flush=True)
    main()
