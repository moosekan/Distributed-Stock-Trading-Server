#!/bin/bash


#BEGIN AI CODE: ChatGPT 4o. Prompt: Provision a t2.medium Ubuntu EC2 instance with SSH and one open service port, checking key pair and security group status.

set -euo pipefail

# === [Step 1] CONFIG ===
KEY_NAME="lab3"
KEY_FILE="$KEY_NAME.pem"
INSTANCE_TYPE="t2.medium"
SECURITY_GROUP="lab3-sg"
UBUNTU_OWNER_ID="099720109477"
REGION="us-east-1"

echo "[Step 1] Checking key pair..."
if [ ! -f "$KEY_FILE" ]; then
  echo " - PEM file $KEY_FILE not found. Please ensure it's in this directory."
  exit 1
fi

# === [Step 2] Security Group Setup ===
echo "[Step 2] Checking or creating security group..."

SG_ID=$(aws ec2 describe-security-groups \
  --group-names $SECURITY_GROUP \
  --query 'SecurityGroups[0].GroupId' \
  --output text 2>/dev/null || true)

if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
  echo " - Security group doesn't exist. Creating..."
  SG_ID=$(aws ec2 create-security-group \
    --group-name $SECURITY_GROUP \
    --description "Lab3 Security Group" \
    --output text \
    --query 'GroupId')
  
  # Allow SSH
  aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 22 \
    --cidr 0.0.0.0/0

  # Allow frontend port
  aws ec2 authorize-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 8091 \
    --cidr 0.0.0.0/0
else
  echo " - Security Group already exists: $SG_ID"
  aws ec2 revoke-security-group-ingress \
    --group-id $SG_ID \
    --protocol tcp \
    --port 8092-8095 \
    --cidr 0.0.0.0/0 || true
fi

# === [Step 3] Find Latest Ubuntu 22.04 AMI ===
echo "[Step 3] Finding latest Ubuntu 22.04 AMI..."
AMI_ID=$(aws ec2 describe-images \
  --owners $UBUNTU_OWNER_ID \
  --filters 'Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*' \
  --query 'Images | sort_by(@, &CreationDate)[-1].ImageId' \
  --output text)

# === [Step 4] Launch EC2 ===
echo "[Step 4] Launching EC2 instance..."

INSTANCE_ID=$(aws ec2 run-instances \
  --image-id $AMI_ID \
  --count 1 \
  --instance-type $INSTANCE_TYPE \
  --key-name $KEY_NAME \
  --security-group-ids $SG_ID \
  --query 'Instances[0].InstanceId' \
  --output text)

# === [Step 5] Wait Until Running ===
echo "[Step 5] Waiting for instance to be in 'running' state..."
aws ec2 wait instance-running --instance-ids $INSTANCE_ID

# === [Step 6] Get Public IP ===
PUBLIC_IP=$(aws ec2 describe-instances \
  --instance-ids $INSTANCE_ID \
  --query 'Reservations[0].Instances[0].PublicIpAddress' \
  --output text)

echo "EC2 instance is running!"
echo "Command to ssh: ssh -i $KEY_FILE ubuntu@$PUBLIC_IP"

#END AI CODE: ChatGPT 4o. Prompt: Provision a t2.medium Ubuntu EC2 instance with SSH and one open service port, checking key pair and security group status.