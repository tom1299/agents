import uuid

from kubernetes import client

from tests.k8s_functions import apply_debug_patch, get_ephemeral_container_status

class TestK8sFunctions:

    def test_apply_debug_patch(self, create_pod_with_image, k8s_core_client: client.CoreV1Api):
        ns = "test-debug-patch"
        pod_name = "test-pod"
        image = "nginx:latest"
        create_pod_with_image(ns, pod_name, image)

        debug_image = "busybox:latest"

        debug_container_names = [f"debug-container-{uuid.uuid4().hex[:8]}" for _ in range(2)]
        for debug_container_name in debug_container_names:

            pod = k8s_core_client.read_namespaced_pod(name=pod_name, namespace=ns)

            command = ["echo", f"hello from {debug_container_name}"]
            updated_pod = apply_debug_patch(k8s_core_client, pod, debug_container_name, debug_image, command)

            assert any(container.name == debug_container_name for container in updated_pod.spec.ephemeral_containers)

            terminated = False
            while not terminated:
                status = get_ephemeral_container_status(k8s_core_client, ns, pod_name, debug_container_name)
                if status and status.state.terminated:
                    terminated = True
                else:
                    import time
                    time.sleep(1)

            logs = k8s_core_client.read_namespaced_pod_log(
                name=pod_name,
                namespace=ns,
                container=debug_container_name,
            )
            assert logs.strip() == f"hello from {debug_container_name}"

        # TODO: Check order of ephemeral containers in the pod
