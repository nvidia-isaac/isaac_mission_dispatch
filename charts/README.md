## Installing Kubernetes

To install kubernetes on a control-plane or worker node, run the following commands:

```
# Install docker
sudo apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release
echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Update /etc/docker/daemon.json
echo '{
    "exec-opts": ["native.cgroupdriver=systemd"],
    "bip": "192.168.222.1/24",
    "dns": ["172.20.232.252","172.20.192.252", "1.1.1.1", "1.0.0.1"],
    "default-address-pools": [
      {
        "base": "10.210.200.0/16",
        "size": 24
      }
    ]
}' | sudo tee /etc/docker/daemon.json
sudo service docker restart

# Install kubernetes
sudo apt-get install -y apt-transport-https ca-certificates curl
sudo curl -fsSLo /usr/share/keyrings/kubernetes-archive-keyring.gpg https://packages.cloud.google.com/apt/doc/apt-key.gpg
echo "deb [signed-by=/usr/share/keyrings/kubernetes-archive-keyring.gpg] https://apt.kubernetes.io/ kubernetes-xenial main" | sudo tee /etc/apt/sources.list.d/kubernetes.list
sudo apt-get update
sudo apt-get install -y kubelet=1.22.1-00 kubeadm=1.22.1-00 kubectl=1.22.1-00
sudo apt-mark hold kubelet kubeadm kubectl

# Disable swap
sudo swapoff -a
```

## Setup Control-plane node

Create a new cluster on the control-plane node:

```
# Start kubernetes
sudo kubeadm init --pod-network-cidr=10.244.0.0/16

# Setup kubeconfig to allow kubectl access to cluster
mkdir -p $HOME/.kube
sudo rm -f  $HOME/.kube/config
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Install flannel
kubectl apply -f charts/kube-flannel.yml

# Install gpu-operator
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia && helm repo update
helm install --create-namespace -n gpu-operator gpu-operator nvidia/gpu-operator
```