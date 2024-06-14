import pytest
import platform

import ray
from ray.cluster_utils import AutoscalingCluster


@pytest.mark.skipif(platform.system() == "Windows", reason="Failing on Windows.")
@pytest.mark.parametrize("autoscaler_v2", [False, True], ids=["v1", "v2"])
def test_fake_autoscaler_basic_e2e(autoscaler_v2, shutdown_only):
    # __example_begin__
    cluster = AutoscalingCluster(
        head_resources={"CPU": 2},
        worker_node_types={
            "cpu_node": {
                "resources": {
                    "CPU": 4,
                    "object_store_memory": 1024 * 1024 * 1024,
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 2,
            },
            "gpu_node": {
                "resources": {
                    "CPU": 2,
                    "GPU": 1,
                    "object_store_memory": 1024 * 1024 * 1024,
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 2,
            },
            "tpu_node": {
                "resources": {
                    "CPU": 2,
                    "TPU": 4,
                    "object_store_memory": 1024 * 1024 * 1024,
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 2,
            },
            "tpu_v5e_node": {
                "resources": {
                    "CPU": 4,
                    "TPU": 8,
                    "object_store_memory": 1024 * 1024 * 1024,
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 2,
            },
        },
        autoscaler_v2=autoscaler_v2,
    )

    try:
        cluster.start()
        ray.init("auto")

        # Triggers the addition of a GPU node.
        @ray.remote(num_gpus=1)
        def f():
            print("gpu ok")

        # Triggers the addition of a CPU node.
        @ray.remote(num_cpus=3)
        def g():
            print("cpu ok")

        # Triggers the addition of a TPU node.
        @ray.remote(resources={"TPU": 4})
        def h():
            print("tpu ok")

        # Triggers the addition of a 8-chip TPU node.
        @ray.remote(resources={"TPU": 8})
        def i():
            print("8-chip tpu ok")

        ray.get(f.remote())
        ray.get(g.remote())
        ray.get(h.remote())
        ray.get(i.remote())
        ray.shutdown()
    finally:
        cluster.shutdown()
    # __example_end__


@pytest.mark.parametrize("autoscaler_v2", [False, True], ids=["v1", "v2"])
def test_zero_cpu_default_actor(autoscaler_v2):
    cluster = AutoscalingCluster(
        head_resources={"CPU": 0},
        worker_node_types={
            "cpu_node": {
                "resources": {
                    "CPU": 1,
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 1,
            },
        },
        autoscaler_v2=autoscaler_v2,
    )

    try:
        cluster.start()
        ray.init("auto")

        @ray.remote
        class Actor:
            def ping(self):
                pass

        actor = Actor.remote()
        ray.get(actor.ping.remote())
        ray.shutdown()
    finally:
        cluster.shutdown()


@pytest.mark.parametrize("autoscaler_v2", [False, True], ids=["v1", "v2"])
def test_autoscaler_cpu_task_gpu_node_up(autoscaler_v2):
    """Validates that CPU tasks can trigger GPU upscaling.
    See https://github.com/ray-project/ray/pull/31202.
    """
    cluster = AutoscalingCluster(
        head_resources={"CPU": 0},
        worker_node_types={
            "gpu_node_type": {
                "resources": {
                    "CPU": 1,
                    "GPU": 1,
                },
                "node_config": {},
                "min_workers": 0,
                "max_workers": 1,
            },
        },
        autoscaler_v2=autoscaler_v2,
    )

    try:
        cluster.start()
        ray.init("auto")

        @ray.remote(num_cpus=1)
        def task():
            return True

        # Make sure the task can be scheduled.
        # Since the head has 0 CPUs, this requires upscaling a GPU worker.
        ray.get(task.remote(), timeout=30)
        ray.shutdown()

    finally:
        cluster.shutdown()


if __name__ == "__main__":
    import os
    import sys

    if os.environ.get("PARALLEL_CI"):
        sys.exit(pytest.main(["-n", "auto", "--boxed", "-vs", __file__]))
    else:
        sys.exit(pytest.main(["-sv", __file__]))
