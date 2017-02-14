"""Connoisseur DataSet Base Class.

Author: Lucas David -- <ld492@drexel.edu>
Licence: MIT License 2016 (c)

"""

import itertools
import math
import os
import shutil
import tarfile
import zipfile
from concurrent.futures import ThreadPoolExecutor
from urllib import request

import numpy as np
from PIL import ImageEnhance, ImageOps
from sklearn.preprocessing import LabelEncoder
from sklearn.utils import check_random_state

from ..utils.image import img_to_array, load_img


class PaintingEnhancer(object):
    def __init__(self, augmentations=('color', 'brightness', 'contrast'),
                 variability=0.5):
        self.augmentations = augmentations
        self.variability = variability

    def process(self, patch):
        if 'color' in self.augmentations:
            enhance = ImageEnhance.Color(patch)
            patch = enhance.enhance(self.variability * np.random.randn() + 1)

        if 'brightness' in self.augmentations:
            enhance = ImageEnhance.Brightness(patch)
            patch = enhance.enhance(self.variability * np.random.randn() + 1)

        if 'contrast' in self.augmentations:
            enhance = ImageEnhance.Contrast(patch)
            patch = enhance.enhance(self.variability * np.random.randn() + 1)
        return patch


class DataSet(object):
    """DataSet Base Class.

    Parameters
    ----------
    base_dir: the directory where the dataset should be downloaded and
        extracted.

    load_mode: ('exact', 'balanced')
        Mode in which the samples are loaded. Options are:
        --- exact: `train_n_patches` patches are extracted from every painting
            in the dataset.
        --- balanced: `train_n_patches` patches are extracted from every
            painting in the dataset. Finally, some paintings are discarded
            until .

    train_n_patches: int, default=50, quantity of patches to extract from
        every training painting.
    test_n_patches: int, default=50, quantity of patches to extract from
        every test painting.

    train_augmentations: list
        List for allowed augmentations performed during loading. Valid values
        are 'color', 'brightness' and 'contrast'.
    test_augmentations: list
        Similar to `train_augmentations`, but applied to `test_data`.

    min_label_rate: float \in [0, 1].
        Minimum rate allowed for labels. All samples of a label which violates
        this bound will be removed before stored in `train_data` and
        `test_data`.
    """

    SOURCE = None
    COMPACTED_FILE = 'dataset.zip'
    EXPECTED_SIZE = 0
    EXTRACTED_FOLDER = None

    generator = None

    def __init__(self, base_dir='./data', load_mode='exact',
                 train_n_patches=50, valid_n_patches=50, test_n_patches=50,
                 image_shape=(224, 224, 3),
                 classes=None, min_label_rate=0,
                 train_augmentations=(),
                 valid_augmentations=(),
                 test_augmentations=(),
                 n_jobs=1,
                 random_state=None):
        self.load_mode = load_mode
        self.base_dir = base_dir
        self.train_n_patches = train_n_patches
        self.valid_n_patches = valid_n_patches
        self.test_n_patches = test_n_patches
        self.image_shape = image_shape
        self.classes = classes
        self.min_label_rate = min_label_rate
        self.train_augmentations = train_augmentations
        self.train_enhancer = PaintingEnhancer(train_augmentations)
        self.valid_augmentations = valid_augmentations
        self.valid_enhancer = PaintingEnhancer(valid_augmentations)
        self.test_augmentations = test_augmentations
        self.test_enhancer = PaintingEnhancer(test_augmentations)
        self.n_jobs = n_jobs
        self.random_state = check_random_state(random_state)

        self.label_encoder_ = None

    @property
    def full_data_path(self):
        return (os.path.join(self.base_dir, self.EXTRACTED_FOLDER)
                if self.EXTRACTED_FOLDER
                else self.base_dir)

    def download(self, override=False):
        os.makedirs(self.base_dir, exist_ok=True)
        file_name = os.path.join(self.base_dir, self.COMPACTED_FILE)

        if os.path.exists(file_name):
            stat = os.stat(file_name)
            if stat.st_size == self.EXPECTED_SIZE and not override:
                print(self.COMPACTED_FILE, 'download skipped.')
                return self

            print('copy corrupted. Re-downloading dataset.')

        print('downloading', self.SOURCE)
        file_name, _ = request.urlretrieve(self.SOURCE, file_name)
        stat = os.stat(file_name)
        print('%s downloaded (%i bytes).' % (self.COMPACTED_FILE, stat.st_size))

        if self.EXPECTED_SIZE and stat.st_size != self.EXPECTED_SIZE:
            raise RuntimeError('File does not have expected size: (%i/%i)' % (
                stat.st_size, self.EXPECTED_SIZE))
        return self

    def extract(self, override=False):
        zipped = os.path.join(self.base_dir, self.COMPACTED_FILE)

        if len(os.listdir(self.base_dir)) > 1 and not override:
            print(self.COMPACTED_FILE, 'extraction skipped.')
        else:
            print('extracting', zipped)
            extractor = self._get_specific_extractor(zipped)
            extractor.extractall(self.base_dir)
            extractor.close()

            print('dataset extracted.')
        return self

    @staticmethod
    def _get_specific_extractor(zipped):
        ext = os.path.splitext(zipped)[1]

        if ext in ('.tar', '.gz', '.tar.gz'):
            return tarfile.open(zipped)
        elif ext == '.zip':
            return zipfile.ZipFile(zipped, 'r')
        else:
            raise RuntimeError('Cannot extract %s. Unknown format.' % zipped)

    def check(self):
        assert os.path.exists(
            self.full_data_path), 'Data set not found. Have you downloaded and extracted it first?'
        return self

    def split_train_valid(self, valid_size):
        base = self.full_data_path

        if os.path.exists(os.path.join(base, 'valid')):
            print('train-valid splitting skipped.')
            return self

        print('splitting train-valid data...')

        labels = os.listdir(os.path.join(base, 'train'))
        files = [list(map(lambda x: os.path.join(l, x),
                          os.listdir(os.path.join(base, 'train', l))))
                 for l in labels]
        files = np.array(list(itertools.chain(*files)))
        self.random_state.shuffle(files)

        valid_split = (valid_size
                       if isinstance(valid_size, int)
                       else int(files.shape[0] * valid_size))

        print('%i/%i files will be used for validation.' % (
            valid_split, files.shape[0]))
        train_files, valid_files = files[valid_split:], files[:valid_split]

        for l in labels:
            os.makedirs(os.path.join(base, 'valid', l), exist_ok=True)

        for file in valid_files:
            shutil.move(os.path.join(base, 'train', file),
                        os.path.join(base, 'valid', file))
        print('splitting done.')
        return self

    def load_patches_from_full_images(self, *phases):
        phases = phases or ('train', 'valid', 'test')
        print('loading %s images' % ','.join(phases))

        results = []
        data_path = self.full_data_path
        image_shape = self.image_shape
        labels = self.classes or os.listdir(os.path.join(data_path, 'train'))

        n_samples_per_label = np.array(
            [len(os.listdir(os.path.join(data_path, 'train', label)))
             for label in labels])
        rates = n_samples_per_label / n_samples_per_label.sum()

        if 'train' in phases:
            print('labels\'s rates: %s' % dict(zip(labels, np.round(rates, 2))))
            print('min tolerated label rate: %.2f' % self.min_label_rate)

        labels = list(map(lambda i: labels[i],
                          filter(lambda i: rates[i] >= self.min_label_rate,
                                 range(len(labels)))))
        min_n_samples = n_samples_per_label.min()

        for phase in phases:
            X, y = [], []

            n_patches = getattr(self, '%s_n_patches' % phase)
            enhancer = getattr(self, '%s_enhancer' % phase)

            if not n_patches:
                continue

            print('extracting %i %s patches...' % (n_patches, phase))
            for label in labels:
                class_path = os.path.join(data_path, phase, label)

                samples = os.listdir(class_path)

                if phase == 'train' and self.load_mode == 'balanced':
                    self.random_state.shuffle(samples)
                    samples = samples[:min_n_samples]

                for name in samples:
                    full_name = os.path.join(class_path, name)
                    img = load_img(full_name)

                    patches = []

                    for _ in range(n_patches):
                        start = (self.random_state.rand(2) *
                                 (img.width - image_shape[1],
                                  img.height - image_shape[0])).astype('int')
                        end = start + (image_shape[1], image_shape[0])
                        patch = img.crop((start[0], start[1], end[0], end[1]))

                        patch = enhancer.process(patch)
                        patches.append(img_to_array(patch))

                    X.append(patches)
                    y.append(label)

            print('%s patches extraction to memory completed.' % phase)

            X = np.array(X, dtype=np.float)

            if phase == 'train':
                self.label_encoder_ = LabelEncoder().fit(y)

            if self.label_encoder_ is None:
                raise ValueError(
                    'you need to load train data first in order to initialize '
                    'the label encoder that will be used to transform the %s data.'
                    % phase)
            y = self.label_encoder_.transform(y)

            results.append((X, y))
        print('loading completed.')
        return results

    def load_patches(self, *phases):
        phases = phases or ('train', 'valid', 'test')
        print('loading %s images patches' % ','.join(phases))

        results = []
        data_path = self.full_data_path
        labels = self.classes or os.listdir(os.path.join(data_path, 'train'))
        r = self.random_state

        for phase in phases:
            n_patches = getattr(self, '%s_n_patches' % phase)
            enhancer = getattr(self, '%s_enhancer' % phase)

            for label in labels:
                label_patch_path = os.path.join(data_path, 'extracted_patches', phase, label)
                samples_names = os.listdir(os.path.join(data_path, phase, label))
                patches_names = os.listdir(label_patch_path)

                X, y = [], []
                for sample in samples_names:
                    sample_patches_names = list(filter(lambda x: sample in x,
                                                       patches_names))
                    if (n_patches is not None
                        and len(sample_patches_names) < n_patches):
                        sample_patches_names = r.choice(sample_patches_names,
                                                        n_patches)
                    else:
                        r.shuffle(sample_patches_names)

                    sample_patches_names = sample_patches_names[:n_patches]

                    _patches = []
                    for sample_patch_name in sample_patches_names:
                        _patches.append(enhancer.process(load_img(
                            os.path.join(label_patch_path,
                                         sample_patch_name))))

                    X.append(np.array(_patches, copy=False))
                    y.append(y)
                y = np.array(y, copy=False)
                results.append((X, y))
        return results

    def extract_patches_to_disk(self):
        print('extracting patches to disk...')

        data_path = self.full_data_path
        labels = self.classes or os.listdir(os.path.join(data_path, 'train'))

        patches_path = os.path.join(data_path, 'extracted_patches')

        os.makedirs(patches_path, exist_ok=True)

        phases = ('train', 'test')
        if os.path.exists(os.path.join(data_path, 'valid')):
            phases += 'valid',

        for phase in phases:
            if os.path.exists(os.path.join(patches_path, phase)):
                print('%s patches extraction to disk skipped.' % phase)
                continue

            print('extracting %s patches to disk...' % phase)

            for label in labels:
                class_path = os.path.join(data_path, phase, label)
                patches_label_path = os.path.join(patches_path, phase, label)
                os.makedirs(patches_label_path)

                samples = os.listdir(class_path)
                with ThreadPoolExecutor(max_workers=self.n_jobs) as executor:
                    list(executor.map(self._extract_image_patches,
                                      [(os.path.join(class_path, n),
                                        patches_label_path)
                                       for n in samples]))

        print('patches extraction completed.')
        return self

    def _extract_image_patches(self, args):
        name, patches_path = args
        image = load_img(name)
        patch_size = self.image_shape
        # Keras (height, width) -> PIL Image (width, height)
        patch_size = [patch_size[1], patch_size[0]]
        border = np.array(patch_size) - image.size
        painting_name = os.path.splitext(os.path.basename(name))[0]

        if np.any(border > 0):
            # The image is smaller than the patch size in any dimension.
            # Pad it to make sure we can extract at least one patch.
            border = np.ceil(border.clip(0, border.max()) / 2).astype(np.int)
            image = ImageOps.expand(image, border=tuple(border))

        n_patches = 0
        for d_width in range(patch_size[0], image.width + 1, patch_size[0]):
            for d_height in range(patch_size[1], image.height + 1,
                                  patch_size[1]):
                e = np.array([d_width, d_height])
                s = e - (patch_size[0], patch_size[1])

                fn = '%s-%i.jpg' % (painting_name, n_patches)
                (image.crop((s[0], s[1], e[0], e[1]))
                 .save(os.path.join(patches_path, fn)))
                n_patches += 1
