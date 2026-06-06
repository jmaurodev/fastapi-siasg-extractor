#!/usr/bin/env bash
#
# EC2 user-data — Amazon Linux 2023
# Sobe o fastapi-siasg-extractor automaticamente no primeiro boot, sem
# intervenção humana: instala dependências, clona o repo e registra um
# serviço systemd que reinicia em falha e volta a subir após reboot.
#
# Cole este conteúdo no campo "User data" ao lançar a instância.
# Logs de execução: /var/log/cloud-init-output.log
#
set -euxo pipefail

REPO_URL="https://github.com/jmaurodev/fastapi-siasg-extractor.git"
APP_DIR="/opt/fastapi-siasg-extractor"
APP_USER="ec2-user"
PYTHON_VERSION="3.14"
PORT=80

# Helper: executa um comando como o usuário da aplicação, com HOME e PATH certos
# (o uv guarda o Python gerenciado e o cache no HOME desse usuário).
run_as_app() {
  sudo -u "$APP_USER" -H env "PATH=/usr/local/bin:/usr/bin:/bin" "$@"
}

# 1) Pacotes base
dnf -y update
dnf -y install git

# 2) uv (gerencia dependências e o próprio Python), instalado system-wide
export UV_INSTALL_DIR="/usr/local/bin"
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3) Código (clone raso da branch main)
rm -rf "$APP_DIR"
git clone --depth 1 "$REPO_URL" "$APP_DIR"
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"

# 4) Python 3.14 (build standalone) + dependências exatas do uv.lock
run_as_app uv python install "$PYTHON_VERSION"
run_as_app uv sync --project "$APP_DIR" --frozen

# 5) Serviço systemd: inicia no boot, reinicia em falha, bind na porta 80
cat >/etc/systemd/system/siasg-extractor.service <<EOF
[Unit]
Description=FastAPI SIASG Extractor
After=network-online.target
Wants=network-online.target

[Service]
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/.venv/bin/uvicorn main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=3
# Permite escutar na porta 80 sem rodar como root.
AmbientCapabilities=CAP_NET_BIND_SERVICE

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now siasg-extractor.service
