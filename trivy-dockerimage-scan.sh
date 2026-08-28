#!/bin/bash

DockerImageName=$(cat Dockerfile | grep "^FROM" | awk '{print $2}')


if [ -z "$DockerImageName"]; then
    echo "NO DOCKER IMAGE FOUND"
    exit 1
fi

echo "Scanning the docker image: $DockerImageName"

trivy image --exit-code 0 --severity HIGH $DockerImageName
trivy image --exit-code 1 --severity HIGH $DockerImageName


exit_code=$?
echo "trivy exit code: $exit_code"


if [ exit_code -eq 1]; then 
    echo "critical vulnarability found"
    exit 1
else
    echo "No   critical vulnarability found"
fi


