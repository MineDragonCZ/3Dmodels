#!/bin/bash

# Define variables
LOCAL_DIR="/home/vojtech/projects/AsterixMicroArm/"
REMOTE_USER="pi"
REMOTE_HOST="147.228.96.157"
REMOTE_DIR="~/projects/"
REMOTE_PROJECT_DIR="~/projects/src"
REMOTE_COMMAND="python Main.py"

# Sync local directory to remote
echo "Starting rsync..."
rsync -avz --delete "$LOCAL_DIR" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR"

if [ $? -eq 0 ]; then
    echo "Rsync completed successfully."
else
    echo "Rsync failed. Exiting."
    exit 1
fi

# SSH into remote and execute commands, keeping the session open
echo "Connecting to $REMOTE_USER@$REMOTE_HOST..."
ssh -t "$REMOTE_USER@$REMOTE_HOST" "
    sudo killall python ;
    cd $REMOTE_PROJECT_DIR && \
    echo 'Running Main.py...' && \
    $REMOTE_COMMAND; \
    bash --login
"
