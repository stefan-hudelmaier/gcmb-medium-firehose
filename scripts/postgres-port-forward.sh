#!/bin/bash

NAMESPACE="default"
LABEL_SELECTOR="app=postgres"

# Find the pod name
POD=$(kubectl get pods -n "$NAMESPACE" -l "$LABEL_SELECTOR" -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD" ]; then
  echo "No pod found with label $LABEL_SELECTOR in namespace $NAMESPACE"
  exit 1
fi

kubectl port-forward -n "$NAMESPACE" "$POD" 5432:5432

