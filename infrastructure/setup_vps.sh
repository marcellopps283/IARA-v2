#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# setup_vps.sh — Script de Setup Inicial da VPS (Executar como root/sudo)
# Google Cloud | Ubuntu 24.04 LTS | 8GB RAM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -e

echo "═══════════════════════════════════════════════"
echo "  🧠 IARA Ecosystem — VPS Bootstrap Script"
echo "═══════════════════════════════════════════════"
echo ""

# ── 1. Atualizar pacotes do sistema ──
echo "📦 Atualizando pacotes do sistema..."
sudo apt-get update && sudo apt-get upgrade -y

# ── 2. Instalar Docker + Docker Compose ──
echo "🐳 Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    sudo usermod -aG docker $USER
    echo "⚠️  Faça logout e login novamente para usar docker sem sudo."
else
    echo "✅ Docker já instalado: $(docker --version)"
fi

# ── 3. Instalar Nginx (se não existir) ──
echo "🌐 Verificando Nginx..."
if ! command -v nginx &> /dev/null; then
    sudo apt-get install -y nginx apache2-utils
    sudo systemctl enable nginx
    echo "✅ Nginx instalado e habilitado."
else
    echo "✅ Nginx já instalado: $(nginx -v 2>&1)"
fi

# ── 4. Instalar Git ──
echo "📚 Verificando Git..."
if ! command -v git &> /dev/null; then
    sudo apt-get install -y git
fi
echo "✅ Git: $(git --version)"

# ── 5. Configurar Firewall (UFW) ──
echo "🔥 Configurando Firewall..."
sudo ufw allow 22/tcp       # SSH
sudo ufw allow 80/tcp       # HTTP
sudo ufw allow 443/tcp      # HTTPS
sudo ufw --force enable
echo "✅ Firewall configurado (22, 80, 443 liberados)."

# ── 6. Criar diretório do projeto ──
PROJECT_DIR="/opt/iara"
echo "📁 Preparando diretório do projeto em ${PROJECT_DIR}..."
sudo mkdir -p ${PROJECT_DIR}
sudo chown -R $USER:$USER ${PROJECT_DIR}

echo ""
echo "═══════════════════════════════════════════════"
echo "  ✅ Setup da VPS concluído!"
echo "═══════════════════════════════════════════════"
echo ""
echo "📋 Próximos passos:"
echo "   1. Clone o repositório para ${PROJECT_DIR}"
echo "   2. Copie .env.example para .env e preencha as chaves"
echo "   3. Execute: cd ${PROJECT_DIR} && docker compose up -d"
echo "   4. Execute: docker compose exec iara-core python bootstrap_routes.py"
echo "   5. Configure o Nginx: bash infrastructure/nginx/setup_nginx_auth.sh"
echo ""
