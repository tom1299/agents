#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

timeout="5m"

if kind get clusters | grep -qx agents-infrastructure; then # grep whole line, suppress output
    echo "Kind cluster agents-infrastructure already exists."
else
    kind create cluster --config kind-config.yaml
fi

if ! pgrep -f cloud-provider-kind >/dev/null; then
    nohup cloud-provider-kind >/tmp/cloud-provider-kind.log 2>&1 &
    echo "Started cloud-provider-kind in the background. Logs are in /tmp/cloud-provider-kind.log"
fi

k8s_mcp_server_ns="kubernetes-mcp-server"
helm upgrade --install kubernetes-mcp-server \
  --namespace "${k8s_mcp_server_ns}" --create-namespace \
  --values kubernetes-mcp-server-values.yaml \
  --wait --timeout "${timeout}" \
  oci://ghcr.io/containers/charts/kubernetes-mcp-server:0.1.1@sha256:263282c4cd1d466edf87e502da277055eebea9b32ecd2471a2ebba3a4b6027eb

kubectl wait pod --all --namespace "${k8s_mcp_server_ns}" --for=condition=Ready --timeout="${timeout}"

flux_operator_ns="flux-system"
helm upgrade --install flux-operator \
  --namespace "${flux_operator_ns}" --create-namespace \
  --wait --timeout "${timeout}" \
  oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator:0.62.1@sha256:1135514a01cc11e206f5ff0b568ac30d9defd675022b7a9da88d4a3474fbdf13

kubectl wait pod --all --namespace "${flux_operator_ns}" --for=condition=Ready --timeout="${timeout}"

helm upgrade --install flux-operator-mcp \
  --namespace "${flux_operator_ns}" \
  --values flux-operator-mcp-values.yaml \
  --wait --timeout "${timeout}" \
  oci://ghcr.io/controlplaneio-fluxcd/charts/flux-operator-mcp:0.62.1@sha256:45ecb9816d751fae12b73940a4f839ea4fe8f5d6fb43ce0989e7f2639e87ffa2

kubectl wait pod -l app.kubernetes.io/name=flux-operator-mcp --namespace "${flux_operator_ns}" --for=condition=Ready --timeout="${timeout}"