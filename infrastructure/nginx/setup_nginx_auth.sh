#!/bin/bash
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# setup_nginx_auth.sh — Configura o Basic Auth no Nginx
# Executar uma vez na VPS antes de ligar o sistema.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

set -e

echo "🔐 Configurando Basic Auth para o Dashboard IARA..."

# Instala o htpasswd se não existir
if ! command -v htpasswd &> /dev/null; then
    echo "Instalando apache2-utils para htpasswd..."
    sudo apt-get update && sudo apt-get install -y apache2-utils
fi

# Solicita o nome de usuário e senha
read -p "Usuário do Dashboard: " DASH_USER
read -sp "Senha do Dashboard: " DASH_PASS
echo ""

# Cria o arquivo .htpasswd
sudo htpasswd -cb /etc/nginx/.htpasswd "$DASH_USER" "$DASH_PASS"

echo "✅ Arquivo /etc/nginx/.htpasswd criado com sucesso!"
echo ""
echo "📋 Próximos passos:"
echo "   1. Copie infrastructure/nginx/iara.conf para /etc/nginx/sites-available/"
echo "   2. Crie um symlink: sudo ln -s /etc/nginx/sites-available/iara.conf /etc/nginx/sites-enabled/"
echo "   3. Teste: sudo nginx -t"
echo "   4. Reinicie: sudo systemctl reload nginx"
