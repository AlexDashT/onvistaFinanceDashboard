#!/usr/bin/env bash

set -euo pipefail

SERVICE_NAME_DEFAULT="onvista-finance-dashboard"
INSTALL_DIR_DEFAULT="/opt/onvistaFinanceDashboard"
REPO_URL_DEFAULT="https://github.com/AlexDashT/onvistaFinanceDashboard.git"
BRANCH_DEFAULT="main"
APP_PORT_DEFAULT="8501"
WEB_SERVER_DEFAULT="caddy"

print_header() {
  echo
  echo "============================================================"
  echo "$1"
  echo "============================================================"
}

prompt_with_default() {
  local prompt_text="$1"
  local default_value="$2"
  local user_value
  read -r -p "$prompt_text [$default_value]: " user_value
  if [[ -z "$user_value" ]]; then
    echo "$default_value"
  else
    echo "$user_value"
  fi
}

prompt_yes_no() {
  local prompt_text="$1"
  local default_value="$2"
  local user_value
  read -r -p "$prompt_text [$default_value]: " user_value
  user_value="${user_value:-$default_value}"
  case "${user_value,,}" in
    y|yes) echo "yes" ;;
    *) echo "no" ;;
  esac
}

require_sudo() {
  if ! command -v sudo >/dev/null 2>&1; then
    echo "This script requires sudo to install packages and configure services."
    exit 1
  fi

  print_header "Checking sudo access"
  sudo -v
}

ensure_user_exists() {
  local target_user="$1"

  if id "$target_user" >/dev/null 2>&1; then
    return
  fi

  print_header "Creating application user"
  sudo useradd --create-home --shell /bin/bash "$target_user"
}

install_base_packages() {
  print_header "Installing base packages"
  sudo apt-get update
  sudo apt-get install -y git curl python3 python3-venv python3-pip python3-dev build-essential
}

install_caddy() {
  print_header "Installing Caddy"
  sudo apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl gpg
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/gpg.key" | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt" | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  sudo chmod o+r /etc/apt/sources.list.d/caddy-stable.list
  sudo apt-get update
  sudo apt-get install -y caddy
}

install_nginx() {
  print_header "Installing Nginx and Certbot"
  sudo apt-get install -y nginx certbot python3-certbot-nginx
}

prepare_checkout() {
  local repo_url="$1"
  local branch="$2"
  local install_dir="$3"
  local app_user="$4"

  print_header "Preparing application checkout"
  sudo mkdir -p "$(dirname "$install_dir")"

  if [[ -d "$install_dir/.git" ]]; then
    local update_existing
    update_existing="$(prompt_yes_no "Existing git checkout found in $install_dir. Update it?" "y")"
    if [[ "$update_existing" == "yes" ]]; then
      sudo git -C "$install_dir" fetch --all
      sudo git -C "$install_dir" checkout "$branch"
      sudo git -C "$install_dir" pull --ff-only origin "$branch"
    else
      echo "Aborting because the install directory already exists."
      exit 1
    fi
  else
    sudo rm -rf "$install_dir"
    sudo git clone --branch "$branch" "$repo_url" "$install_dir"
  fi

  sudo chown -R "$app_user":"$app_user" "$install_dir"
}

setup_virtualenv() {
  local install_dir="$1"
  local app_user="$2"

  print_header "Creating virtual environment and installing Python dependencies"
  sudo -u "$app_user" python3 -m venv "$install_dir/.venv"
  sudo -u "$app_user" "$install_dir/.venv/bin/pip" install --upgrade pip
  sudo -u "$app_user" "$install_dir/.venv/bin/pip" install -r "$install_dir/requirements.txt"
}

install_playwright_if_requested() {
  local install_dir="$1"
  local app_user="$2"
  local install_playwright="$3"

  if [[ "$install_playwright" != "yes" ]]; then
    return
  fi

  print_header "Installing Playwright Chromium"
  sudo -u "$app_user" "$install_dir/.venv/bin/python" -m playwright install chromium
}

ensure_data_directories() {
  local install_dir="$1"
  local app_user="$2"

  print_header "Preparing writable data directories"
  sudo -u "$app_user" mkdir -p "$install_dir/data/cache" "$install_dir/data/exports"
}

write_systemd_service() {
  local service_name="$1"
  local install_dir="$2"
  local app_user="$3"
  local app_port="$4"

  print_header "Writing systemd service"
  sudo tee "/etc/systemd/system/${service_name}.service" >/dev/null <<EOF
[Unit]
Description=onvistaFinanceDashboard Streamlit service
After=network.target

[Service]
Type=simple
User=${app_user}
WorkingDirectory=${install_dir}
Environment=PYTHONUNBUFFERED=1
ExecStart=${install_dir}/.venv/bin/python -m streamlit run ${install_dir}/app.py --server.address 127.0.0.1 --server.port ${app_port} --server.headless true
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  sudo systemctl daemon-reload
  sudo systemctl enable --now "${service_name}.service"
}

configure_caddy() {
  local service_name="$1"
  local domain_name="$2"
  local app_port="$3"

  print_header "Configuring Caddy"
  sudo mkdir -p /etc/caddy/conf.d

  if ! sudo grep -q "import /etc/caddy/conf.d/\*.caddy" /etc/caddy/Caddyfile; then
    echo "" | sudo tee -a /etc/caddy/Caddyfile >/dev/null
    echo "import /etc/caddy/conf.d/*.caddy" | sudo tee -a /etc/caddy/Caddyfile >/dev/null
  fi

  sudo tee "/etc/caddy/conf.d/${service_name}.caddy" >/dev/null <<EOF
${domain_name} {
  reverse_proxy 127.0.0.1:${app_port}
  encode gzip zstd
}
EOF

  sudo systemctl reload caddy
}

configure_nginx() {
  local service_name="$1"
  local domain_name="$2"
  local app_port="$3"
  local letsencrypt_email="$4"

  print_header "Configuring Nginx"
  sudo tee "/etc/nginx/sites-available/${service_name}" >/dev/null <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${domain_name};

    location / {
        proxy_pass http://127.0.0.1:${app_port};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

  sudo ln -sf "/etc/nginx/sites-available/${service_name}" "/etc/nginx/sites-enabled/${service_name}"
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t
  sudo systemctl enable --now nginx
  sudo systemctl reload nginx

  if [[ -n "$letsencrypt_email" ]]; then
    print_header "Requesting HTTPS certificate with Certbot"
    sudo certbot --nginx --non-interactive --agree-tos -m "$letsencrypt_email" -d "$domain_name" --redirect
  else
    echo "Skipping Certbot because no email address was provided."
  fi
}

configure_firewall() {
  local configure_ufw="$1"

  if [[ "$configure_ufw" != "yes" ]]; then
    return
  fi

  if ! command -v ufw >/dev/null 2>&1; then
    echo "ufw is not installed. Skipping firewall configuration."
    return
  fi

  print_header "Configuring firewall"
  sudo ufw allow OpenSSH
  sudo ufw allow 80/tcp
  sudo ufw allow 443/tcp
  sudo ufw --force enable
}

show_summary() {
  local service_name="$1"
  local install_dir="$2"
  local domain_name="$3"
  local web_server="$4"

  print_header "Deployment complete"
  echo "Application directory: $install_dir"
  echo "Service name: $service_name"
  echo "Reverse proxy: $web_server"
  if [[ -n "$domain_name" ]]; then
    echo "Expected URL: https://$domain_name"
  else
    echo "Expected local URL: http://127.0.0.1:8501"
  fi
  echo
  sudo systemctl status "$service_name" --no-pager || true
}

main() {
  require_sudo

  print_header "onvistaFinanceDashboard Ubuntu deployment"
  echo "This script installs the app, creates a systemd service, and configures a reverse proxy."
  echo "Recommended default: Caddy, because it is simpler and handles HTTPS automatically."

  local default_user
  default_user="${SUDO_USER:-$USER}"

  local service_name
  local install_dir
  local repo_url
  local branch
  local app_port
  local app_user
  local domain_name
  local web_server
  local install_playwright
  local configure_ufw
  local letsencrypt_email=""

  service_name="$(prompt_with_default "Systemd service name" "$SERVICE_NAME_DEFAULT")"
  install_dir="$(prompt_with_default "Install directory" "$INSTALL_DIR_DEFAULT")"
  repo_url="$(prompt_with_default "Git repository URL" "$REPO_URL_DEFAULT")"
  branch="$(prompt_with_default "Git branch" "$BRANCH_DEFAULT")"
  app_port="$(prompt_with_default "Internal Streamlit port" "$APP_PORT_DEFAULT")"
  app_user="$(prompt_with_default "Linux user that should run the app" "$default_user")"
  domain_name="$(prompt_with_default "Domain or subdomain for the app" "")"
  web_server="$(prompt_with_default "Reverse proxy (caddy or nginx) - default is recommended" "$WEB_SERVER_DEFAULT")"
  install_playwright="$(prompt_yes_no "Install Playwright Chromium too? (not required for current features)" "n")"
  configure_ufw="$(prompt_yes_no "Configure ufw firewall for SSH, HTTP, and HTTPS?" "y")"

  web_server="${web_server,,}"
  if [[ "$web_server" != "caddy" && "$web_server" != "nginx" ]]; then
    echo "Unsupported reverse proxy: $web_server"
    exit 1
  fi

  if [[ -z "$domain_name" ]]; then
    echo "A domain or subdomain is strongly recommended for production deployment."
    local continue_without_domain
    continue_without_domain="$(prompt_yes_no "Continue without a domain?" "n")"
    if [[ "$continue_without_domain" != "yes" ]]; then
      exit 1
    fi
  fi

  if [[ "$web_server" == "nginx" ]]; then
    letsencrypt_email="$(prompt_with_default "Email for Let's Encrypt (leave blank to skip HTTPS)" "")"
  fi

  ensure_user_exists "$app_user"
  install_base_packages

  if [[ "$web_server" == "caddy" ]]; then
    install_caddy
  else
    install_nginx
  fi

  prepare_checkout "$repo_url" "$branch" "$install_dir" "$app_user"
  setup_virtualenv "$install_dir" "$app_user"
  install_playwright_if_requested "$install_dir" "$app_user" "$install_playwright"
  ensure_data_directories "$install_dir" "$app_user"
  write_systemd_service "$service_name" "$install_dir" "$app_user" "$app_port"

  if [[ -n "$domain_name" ]]; then
    if [[ "$web_server" == "caddy" ]]; then
      configure_caddy "$service_name" "$domain_name" "$app_port"
    else
      configure_nginx "$service_name" "$domain_name" "$app_port" "$letsencrypt_email"
    fi
  fi

  configure_firewall "$configure_ufw"
  show_summary "$service_name" "$install_dir" "$domain_name" "$web_server"
}

main "$@"
