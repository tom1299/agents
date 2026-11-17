from unittest.mock import Mock, call

import pytest
from kubernetes.client.rest import ApiException

from tests import fixtures


@pytest.fixture
def manifest_fixture(monkeypatch):
    resources = {
        "ConfigMap": Mock(namespaced=True),
        "Deployment": Mock(namespaced=True),
        "Namespace": Mock(namespaced=False),
    }
    dynamic_client = Mock()
    dynamic_client.resources.get.side_effect = lambda *, api_version, kind: resources[kind]
    monkeypatch.setattr(fixtures.dynamic, "DynamicClient", lambda api_client: dynamic_client)
    create_namespace = Mock()
    generator = fixtures.apply_manifest.__wrapped__(Mock(), create_namespace)
    apply = next(generator)
    yield apply, resources, create_namespace, generator
    try:
        next(generator)
    except StopIteration:
        pass


@pytest.mark.parametrize(
    "document, message",
    [
        ("apiVersion: v1\nkind: Namespace\nmetadata:\n  name: other\n", "Cluster-scoped"),
        ("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: x\n  namespace: other\n", "Namespace mismatch"),
    ],
)
def test_apply_manifest_rejects_out_of_scope_resources(manifest_fixture, tmp_path, document, message):
    apply, resources, create_namespace, _ = manifest_fixture
    manifest = tmp_path / "invalid.yaml"
    manifest.write_text(document)
    with pytest.raises(ValueError, match=message):
        apply(str(manifest), "test")
    create_namespace.assert_not_called()
    resources["ConfigMap"].server_side_apply.assert_not_called()


def test_apply_manifest_cleans_up_after_partial_failure(manifest_fixture, tmp_path):
    apply, resources, _, generator = manifest_fixture
    manifest = tmp_path / "resources.yaml"
    manifest.write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: config\n"
        "---\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: app\n"
    )
    resources["Deployment"].server_side_apply.side_effect = ApiException(status=403)

    with pytest.raises(ApiException):
        apply(str(manifest), "test")
    with pytest.raises(StopIteration):
        next(generator)
    resources["Deployment"].delete.assert_called_once_with(name="app", namespace="test")
    resources["ConfigMap"].delete.assert_called_once_with(name="config", namespace="test")


def test_apply_manifest_reports_cleanup_errors_after_remaining_deletes(manifest_fixture, tmp_path):
    apply, resources, _, generator = manifest_fixture
    manifest = tmp_path / "resources.yaml"
    manifest.write_text(
        "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: config\n"
        "---\napiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: app\n"
    )
    apply(str(manifest), "test")
    resources["Deployment"].delete.side_effect = ApiException(status=403)

    with pytest.raises(ExceptionGroup, match="Failed to delete manifest resources"):
        next(generator)
    resources["ConfigMap"].delete.assert_called_once_with(name="config", namespace="test")


def test_apply_manifest_rejects_empty_manifest(manifest_fixture, tmp_path):
    apply, _, create_namespace, _ = manifest_fixture
    manifest = tmp_path / "empty.yaml"
    manifest.write_text("---\n")
    with pytest.raises(ValueError, match="No resources"):
        apply(str(manifest), "test")
    create_namespace.assert_not_called()
