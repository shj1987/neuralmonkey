"""Encoder for sentence classification with 1D convolutions and max-pooling."""

from typing import Tuple, List

from typeguard import check_argument_types
import tensorflow as tf

from neuralmonkey.dataset import Dataset
from neuralmonkey.decorators import tensor
from neuralmonkey.model.feedable import FeedDict
from neuralmonkey.model.parameterized import InitializerSpecs
from neuralmonkey.model.model_part import ModelPart
from neuralmonkey.model.stateful import Stateful
from neuralmonkey.nn.utils import dropout
from neuralmonkey.vocabulary import Vocabulary
from neuralmonkey.tf_utils import get_variable


class SequenceCNNEncoder(ModelPart, Stateful):
    """Encoder processing a sequence using a CNN."""

    # pylint: disable=too-many-arguments
    def __init__(self,
                 name: str,
                 vocabulary: Vocabulary,
                 data_id: str,
                 embedding_size: int,
                 filters: List[Tuple[int, int]],
                 max_input_len: int = None,
                 dropout_keep_prob: float = 1.0,
                 reuse: ModelPart = None,
                 save_checkpoint: str = None,
                 load_checkpoint: str = None,
                 initializers: InitializerSpecs = None) -> None:
        """Create a new instance of the CNN sequence encoder.

        Based on: Yoon Kim: Convolutional Neural Networks for Sentence
        Classification (http://emnlp2014.org/papers/pdf/EMNLP2014181.pdf)

        Arguments:
            vocabulary: Input vocabulary
            data_id: Identifier of the data series fed to this encoder
            name: An unique identifier for this encoder
            max_input_len: Maximum length of an encoded sequence
            embedding_size: The size of the embedding vector assigned
                to each word
            filters: Specification of CNN filters. It is a list of tuples
                specifying the filter size and number of channels.
            dropout_keep_prob: The dropout keep probability
                (default 1.0)
        """
        check_argument_types()
        ModelPart.__init__(self, name, reuse, save_checkpoint, load_checkpoint,
                           initializers)

        self.vocabulary = vocabulary
        self.data_id = data_id
        self.max_input_len = max_input_len
        self.embedding_size = embedding_size
        self.dropout_keep_prob = dropout_keep_prob
        self.filters = filters

        with self.use_scope():
            self.inputs = tf.placeholder(
                tf.int32, [None, None], "encoder_input")
            self.input_mask = tf.placeholder(
                tf.float32, [None, None], "encoder_padding")

    @tensor
    def embedded_inputs(self) -> tf.Tensor:
        with tf.variable_scope("input_projection"):
            embedding_matrix = get_variable(
                "word_embeddings",
                [len(self.vocabulary), self.embedding_size],
                initializer=tf.variance_scaling_initializer(
                    mode="fan_avg", distribution="uniform"))
            return dropout(
                tf.nn.embedding_lookup(embedding_matrix, self.inputs),
                self.dropout_keep_prob,
                self.train_mode)

    @tensor
    def output(self) -> tf.Tensor:
        pooled_outputs = []
        for filter_size, num_filters in self.filters:
            with tf.variable_scope("conv-maxpool-%s" % filter_size):
                # Convolution Layer
                filter_shape = [filter_size, self.embedding_size, num_filters]
                w_filter = get_variable(
                    "conv_W", filter_shape,
                    initializer=tf.variance_scaling_initializer(
                        mode="fan_avg", distribution="uniform"))
                b_filter = get_variable(
                    "conv_bias", [num_filters],
                    initializer=tf.zeros_initializer())
                conv = tf.nn.conv1d(
                    self.embedded_inputs,
                    w_filter,
                    stride=1,
                    padding="VALID",
                    name="conv")

                # Apply nonlinearity
                conv_relu = tf.nn.relu(tf.nn.bias_add(conv, b_filter))

                # Max-pooling over the outputs
                pooled = tf.reduce_max(conv_relu, 1)
                pooled_outputs.append(pooled)

        # Combine all the pooled features
        return tf.concat(pooled_outputs, axis=1)

    def feed_dict(self, dataset: Dataset, train: bool = False) -> FeedDict:
        """Populate the feed dictionary with the encoder inputs.

        Arguments:
            dataset: The dataset to use
            train: Boolean flag telling whether it is training time
        """
        fd = ModelPart.feed_dict(self, dataset, train)

        sentences = dataset.get_series(self.data_id)
        vectors, paddings = self.vocabulary.sentences_to_tensor(
            list(sentences), self.max_input_len, pad_to_max_len=False,
            train_mode=train)

        # as sentences_to_tensor returns lists of shape (time, batch),
        # we need to transpose
        fd[self.inputs] = list(zip(*vectors))
        fd[self.input_mask] = list(zip(*paddings))

        return fd
