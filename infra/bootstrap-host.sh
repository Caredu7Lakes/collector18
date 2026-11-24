#!/usr/bin/env bash
# infra/bootstrap-host.sh — prepara um host Ubuntu 24.04 limpo p/ rodar o collector18.
# Idempotente: swap e Docker so instalam se faltarem. Rodar como 'ubuntu' (usa sudo).
set -euo pipefail

SWAP_GB="${SWAP_GB:-2}"

echo "== Swap ${SWAP_GB}G =="
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l "${SWAP_GB}G" /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  echo "swap criado e persistido no fstab"
else
  echo "swap ja ativo"
fi

echo "== Docker CE + compose plugin =="
if ! command -v docker >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y ca-certificates curl gnupg git
  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  sudo usermod -aG docker "$USER"
  echo "Docker instalado. Rode 'newgrp docker' (ou faca logout/login) p/ usar sem sudo."
else
  echo "docker ja instalado: $(docker --version)"
fi

echo "== Host pronto. Proximo: criar .env e 'docker compose up -d --build'. =="
