# Lint as: python2, python3
# Copyright 2019 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""E2E Tests for tfx.examples.chicago_taxi_pipeline.taxi_pipeline_importer."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
from typing import Text

import tensorflow as tf
from tfx_bsl.version import __version__ as tfx_bsl_version

from tfx.examples.chicago_taxi_pipeline import taxi_pipeline_importer
from tfx.orchestration import metadata
from tfx.orchestration.beam.beam_dag_runner import BeamDagRunner


class TaxiPipelineImporterEndToEndTest(tf.test.TestCase):

  def setUp(self):
    super(TaxiPipelineImporterEndToEndTest, self).setUp()
    self._test_dir = os.path.join(
        os.environ.get('TEST_UNDECLARED_OUTPUTS_DIR', self.get_temp_dir()),
        self._testMethodName)

    self._pipeline_name = 'beam_test'
    self._data_root = os.path.join(os.path.dirname(__file__), 'data', 'simple')
    self._user_schema_path = os.path.join(
        os.path.dirname(__file__), 'data', 'user_provided_schema')
    self._module_file = os.path.join(os.path.dirname(__file__), 'taxi_utils.py')
    self._serving_model_dir = os.path.join(self._test_dir, 'serving_model')
    self._pipeline_root = os.path.join(self._test_dir, 'tfx', 'pipelines',
                                       self._pipeline_name)
    self._metadata_path = os.path.join(self._test_dir, 'tfx', 'metadata',
                                       self._pipeline_name, 'metadata.db')

  def assertExecutedOnce(self, component: Text) -> None:
    """Check the component is executed exactly once."""
    component_path = os.path.join(self._pipeline_root, component)
    self.assertTrue(tf.io.gfile.exists(component_path))
    outputs = tf.io.gfile.listdir(component_path)
    for output in outputs:
      execution = tf.io.gfile.listdir(os.path.join(component_path, output))
      self.assertEqual(1, len(execution))

  def assertPipelineExecution(self) -> None:
    self.assertExecutedOnce('CsvExampleGen')
    self.assertExecutedOnce('Evaluator')
    self.assertExecutedOnce('ExampleValidator')
    self.assertExecutedOnce('Pusher')
    self.assertExecutedOnce('SchemaGen')
    self.assertExecutedOnce('StatisticsGen')
    self.assertExecutedOnce('Trainer')
    self.assertExecutedOnce('Transform')

  def testTaxiPipelineWithImporter(self):
    BeamDagRunner().run(
        taxi_pipeline_importer._create_pipeline(
            pipeline_name=self._pipeline_name,
            data_root=self._data_root,
            user_schema_path=self._user_schema_path,
            module_file=self._module_file,
            serving_model_dir=self._serving_model_dir,
            pipeline_root=self._pipeline_root,
            metadata_path=self._metadata_path,
            beam_pipeline_args=[]))

    self.assertTrue(tf.io.gfile.exists(self._serving_model_dir))
    self.assertTrue(tf.io.gfile.exists(self._metadata_path))
    metadata_config = metadata.sqlite_metadata_connection_config(
        self._metadata_path)
    with metadata.Metadata(metadata_config) as m:
      artifact_count = len(m.store.get_artifacts())
      execution_count = len(m.store.get_executions())
      self.assertGreaterEqual(artifact_count, execution_count)
      self.assertEqual(10, execution_count)

    self.assertPipelineExecution()

    # Runs the pipeline again.
    BeamDagRunner().run(
        taxi_pipeline_importer._create_pipeline(
            pipeline_name=self._pipeline_name,
            data_root=self._data_root,
            user_schema_path=self._user_schema_path,
            module_file=self._module_file,
            serving_model_dir=self._serving_model_dir,
            pipeline_root=self._pipeline_root,
            metadata_path=self._metadata_path,
            beam_pipeline_args=[]))

    # All executions but Evaluator and Pusher are cached.
    # Note that Resolver will always execute.
    with metadata.Metadata(metadata_config) as m:
      # Artifact count is increased by 3 caused by Evaluator and Pusher.
      self.assertEqual(artifact_count + 3, len(m.store.get_artifacts()))
      artifact_count = len(m.store.get_artifacts())
      self.assertEqual(20, len(m.store.get_executions()))

    # Runs the pipeline the third time.
    BeamDagRunner().run(
        taxi_pipeline_importer._create_pipeline(
            pipeline_name=self._pipeline_name,
            data_root=self._data_root,
            user_schema_path=self._user_schema_path,
            module_file=self._module_file,
            serving_model_dir=self._serving_model_dir,
            pipeline_root=self._pipeline_root,
            metadata_path=self._metadata_path,
            beam_pipeline_args=[]))

    # Asserts cache execution.
    with metadata.Metadata(metadata_config) as m:
      # Artifact count is unchanged.
      self.assertEqual(artifact_count, len(m.store.get_artifacts()))
      self.assertEqual(30, len(m.store.get_executions()))


if __name__ == '__main__':
  tf.test.main()
