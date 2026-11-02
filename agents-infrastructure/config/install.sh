#!/usr/bin/env bash

set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

namespace="kubernetes-mcp-server"
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

if helm status "${namespace}" --namespace "${namespace}" >/dev/null 2>&1; then
    echo "Helm release ${namespace} already installed."
else
    helm upgrade --install "${namespace}" \
        --namespace "${namespace}" --create-namespace \
        --version 0.1.1 \
        --values kubernetes-mcp-server-values.yaml \
        --wait --timeout "${timeout}" \
        oci://ghcr.io/containers/charts/kubernetes-mcp-server@sha256:263282c4cd1d466edf87e502da277055eebea9b32ecd2471a2ebba3a4b6027eb

    kubectl wait pod --all --namespace "${namespace}" --for=condition=Ready --timeout="${timeout}"
fi
