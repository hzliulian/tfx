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
"""Experimental Resolver for getting the latest artifact."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from typing import Dict, List, Optional, Text

from tfx import types
from tfx.dsl.resolvers import base_resolver
from tfx.orchestration import data_types
from tfx.orchestration import metadata
from tfx.types import artifact_utils


def _time_order(artifact: types.Artifact):
  # Use MLMD Artifact.id for tie breaking so that result is deterministic.
  return (artifact.mlmd_artifact.last_update_time_since_epoch, artifact.id)


class LatestArtifactsResolver(base_resolver.BaseResolver):
  """Resolver that return the latest n artifacts in a given channel.

  Note that this Resolver is experimental and is subject to change in terms of
  both interface and implementation.
  """

  def __init__(self, desired_num_of_artifacts: int = 1):
    self._desired_num_of_artifact = desired_num_of_artifacts

  def _resolve(self, input_dict: Dict[Text, List[types.Artifact]]):
    result = {}
    for k, artifact_list in input_dict.items():
      sorted_artifact_list = sorted(artifact_list, key=_time_order)
      result[k] = sorted_artifact_list[-self._desired_num_of_artifact:]
    return result

  def resolve(
      self,
      pipeline_info: data_types.PipelineInfo,
      metadata_handler: metadata.Metadata,
      source_channels: Dict[Text, types.Channel],
  ) -> base_resolver.ResolveResult:
    pipeline_context = metadata_handler.get_pipeline_context(pipeline_info)
    if pipeline_context is None:
      raise RuntimeError('Pipeline context absent for %s' % pipeline_context)

    candidate_dict = {}
    for k, c in source_channels.items():
      cancidate_artifacts = metadata_handler.get_qualified_artifacts(
          contexts=[pipeline_context],
          type_name=c.type_name,
          producer_component_id=c.producer_component_id,
          output_key=c.output_key)
      candidate_dict[k] = [
          artifact_utils.deserialize_artifact(a.type, a.artifact)
          for a in cancidate_artifacts
      ]

    resolved_dict = self._resolve(candidate_dict)
    resolve_state_dict = {
        k: len(artifact_list) >= self._desired_num_of_artifact
        for k, artifact_list in resolved_dict.items()
    }

    return base_resolver.ResolveResult(
        per_key_resolve_result=resolved_dict,
        per_key_resolve_state=resolve_state_dict)

  def resolve_artifacts(
      self, context: base_resolver.ResolverContext,
      input_dict: Dict[Text, List[types.Artifact]]
  ) -> Optional[Dict[Text, List[types.Artifact]]]:
    """Resolves artifacts from channels by querying MLMD.

    Args:
      context: A ResolverContext for resolver runtime.
      input_dict: The input_dict to resolve from.

    Returns:
      If `min_count` for every input is met, returns a
      Dict[Text, List[Artifact]]. Otherwise, return None.
    """
    resolved_dict = self._resolve(input_dict)
    all_min_count_met = all(
        len(artifact_list) >= self._desired_num_of_artifact
        for artifact_list in resolved_dict.values())
    return resolved_dict if all_min_count_met else None
