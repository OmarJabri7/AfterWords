#!/bin/bash

# Config
IMAGE_NAME="after_words-test"
CONTAINER_NAME="after_words-container"
PORT=8000

# Step 1: Build the Docker image
echo "🛠️  Building Docker image..."
docker build -t $IMAGE_NAME . --file src/containers/Dockerfile

# Step 2: Stop any running container with the same name
echo "🧹 Cleaning up old container (if any)..."
docker rm -f $CONTAINER_NAME 2>/dev/null || true

# Step 3: Run the container
echo "🚀 Starting container..."
docker run -d --name $CONTAINER_NAME -p $PORT:8000 $IMAGE_NAME

# Step 4: Wait briefly for the server to start
echo "⏳ Waiting for the server to start..."
sleep 3

# Step 5: Test endpoint
echo "📡 Testing / endpoint..."
curl -v http://localhost:$PORT/

docker logs after_words-container

# Step 6: Optionally stop container (uncomment to auto-clean)
# echo "🧽 Stopping container..."
# docker stop $CONTAINER_NAME && docker rm $CONTAINER_NAME