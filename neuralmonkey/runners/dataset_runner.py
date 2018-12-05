from typing import List, Dict
import numpy as np
import tensorflow as tf

from neuralmonkey.decorators import tensor
from neuralmonkey.model.feedable import Feedable
from neuralmonkey.runners.base_runner import GraphExecutor


class DatasetRunner(GraphExecutor, Feedable):

    # pylint: disable=too-few-public-methods
    # Pylint issue here: https://github.com/PyCQA/pylint/issues/2607
    class Executable(GraphExecutor.Executable["DatasetRunner"]):

        def collect_results(self, results: List[Dict]) -> None:
            res = results[0]

            # Take care of nested data series (such as Audio in tests/ctc.ini)
            for s_id in res:
                if not tf.contrib.framework.nest.is_sequence(
                        self.executor.dataset[s_id]):
                    continue

                res[s_id] = list(zip(*tf.contrib.framework.nest.flatten_up_to(
                    self.executor.dataset[s_id], res[s_id])))

            for s_id in res:
                if s_id in self.executor.string_series:
                    res[s_id] = tf.contrib.framework.nest.map_structure(
                        tf.compat.as_text,
                        tf.contrib.framework.nest.map_structure(
                            np.ndarray.tolist,
                            res[s_id]))

            data = [dict(zip(res, series)) for series in zip(*res.values())]

            self.set_result(data, [], None, None, None)
    # pylint: enable=too-few-public-methods

    def __init__(self) -> None:
        GraphExecutor.__init__(self, set())
        Feedable.__init__(self)

        self.string_series = []  # type: List[str]

    def register_input(self, dataset: tf.data.Dataset) -> None:
        super().register_input(dataset)
        self.string_series = [
            key for key in dataset if hasattr(
                dataset[key], "dtype") and dataset[key].dtype == tf.string]

    @tensor
    def fetches(self) -> Dict[str, tf.Tensor]:
        assert self.dataset is not None
        return self.dataset