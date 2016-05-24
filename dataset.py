""" Iplementation of the dataset class. """

import codecs
import magic
import numpy as np

from utils import log
from vocabulary import Vocabulary

class Dataset(object):
    """
    This class serves as collection for data series for particular
    encoders and decoders in the model. If it is not provided a parent
    dataset, it also manages the vocabularies inferred from the data.

    A data serie is either list of strings or a numpy array.

    Attributes:

        series: Dictionary from the series name to the actual data.

        series_languages: Dictionary from the series name to their language.

    """

    def __init__(self, **args):
        """

        Creates a dataset from the provided arguments. Path to the data are
        provided in a form dictionary.

        Only textual datasets from the textual datasets for which the language
        was provided a vocabulary can be generated.

        Args:

            args: Arguements treated as a dictionary. Paths to the data series
                are specified here. Series identifiers should not contain
                underscore. You can scecify a language fo the serie by adding

                <identifier>_lng="language"

                and a preprocess method you want to
                apply on the textual data by naming the function as
                <identifier>_preprocess=function.

        """

        if 'name' in args:
            self.name = args['name']
        else:
            self.name = "dataset"

        series_names = [k for k in args.keys() if k.find('_') == -1]
        log("Initializing dataset with: {}".format(", ".join(series_names)))

        def create_serie(name, path):
            """ Loads a data serie from a file """
            log("Loading {}".format(path))
            file_type = magic.from_file(path, mime=True)

            # if the dataset has no name, generate it from files
            if 'name' not in args:
                self.name += "-"+path

            if file_type == 'text/plain':
                if name+"_preprocess" in args:
                    preprocess = args[name+"_preprocess"]
                else:
                    preprocess = lambda s: s.split(" ")

                with codecs.open(path, 'r', 'utf-8') as f_data:
                    return list([preprocess(line.rstrip()) for line in f_data])
            elif file_type == 'application/octet-stream':
                return np.load(path)


        self.series = {name: create_serie(name, args[name]) for name in series_names}

        assert len(set([len(v) for v in self.series.values()])) == 1

        self.series_outputs = \
                {key[:-4]: value for key, value in args.iteritems() if key.endswith('_out')}

        self.series_languages = {}
        for name, serie in self.series.iteritems():
            if isinstance(serie, list) and name+"_lng" in args:
                language = args[name+"_lng"]
                self.series_languages[name] = language

        if 'random_seed' in args:
            self.random_seed = args['random_seed']
        else:
            self.random_seed = None

        log("Dataset loaded, {} examples.".format(len(self)))

    def __len__(self):
        return len(self.series.values()[0])

    def create_vocabularies(self, max_vocabulary_size=None):
        """
        Gets dictionary of vocabularies created for each language in the dataset.
        """

        vocabularies = dict()

        for name, serie in self.series.iteritems():
            if isinstance(serie, list) and name in self.series_languages:
                language = self.series_languages[name]
                if language in vocabularies:
                    vocabulary = vocabularies[language]
                else:
                    vocabulary = Vocabulary(random_seed=self.random_seed)
                    vocabularies[language] = vocabulary
                vocabulary.add_tokenized_text([token for sent in serie for token in sent])

        if max_vocabulary_size is not None:
            for voc in vocabularies.values():
                voc.trunkate(max_vocabulary_size)

        return vocabularies

    def shuffle(self):
        """ Shuffles the dataset randomly """
        pass

    def batch_serie(self, serie_name, batch_size):
        """ Splits a data serie into batches """
        serie = self.series[serie_name]
        for start in range(0, len(serie), batch_size):
            yield serie[start:start+batch_size]
