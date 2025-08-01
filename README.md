# Backend - Controle de Produção

Backend seguro e limpo para o sistema de controle de produção da empresa.

## 🚀 Funcionalidades

- ✅ **API REST** para salvar registros de produção
- ✅ **CORS configurado** para integração com frontend
- ✅ **Endpoints seguros** sem exposição de credenciais
- ✅ **Estrutura limpa** e organizada
- ✅ **Deploy otimizado** para Render/Railway

## 📋 Endpoints Disponíveis

### `GET /api/health`
Verifica se o backend está funcionando.

### `POST /api/salvar-registro`
Salva um novo registro de produção.

**Body (JSON):**
```json
{
  "data": "2024-01-15",
  "operador": "João Silva",
  "turno": "1",
  "toneladas": "150.5",
  "silos": [...],
  "paradas": [...],
  "testeZeroGraos": [...],
  "observacoes": "..."
}
```

### `GET /api/listar-registros`
Lista todos os registros salvos.

### `GET /api/registro/<id>`
Obtém um registro específico por ID.

### `GET /api/estatisticas`
Obtém estatísticas dos registros.

## 🛠️ Como Executar Localmente

```bash
# Ativar ambiente virtual
source venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Executar servidor
python src/main.py
```

## 🌐 Deploy

### Render
1. Conectar repositório GitHub
2. Configurar build command: `pip install -r requirements.txt`
3. Configurar start command: `python src/main.py`
4. Definir PORT como variável de ambiente

### Railway
1. Conectar repositório GitHub
2. Deploy automático

## 🔒 Segurança

- ❌ **Sem credenciais expostas** no código
- ✅ **Variáveis de ambiente** para configurações sensíveis
- ✅ **CORS configurado** adequadamente
- ✅ **Gitignore robusto** para arquivos sensíveis

## 📝 Versão

**v2.0.0** - Backend limpo e seguro

