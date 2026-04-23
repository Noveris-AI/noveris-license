# naviam-license

Naviam License Platform - 面向企业私有化交付的许可证签发、激活、续签、校验与吊销系统。

## 项目结构

```
naviam-license/
├── backend/
│   ├── api/                 # FastAPI 后端
│   │   ├── app/
│   │   │   ├── core/        # 配置、安全、session、错误处理、分页
│   │   │   ├── db/          # 数据库迁移 (Alembic)
│   │   │   ├── modules/
│   │   │   │   ├── issue/   # License 签发、运营人员认证
│   │   │   │   └── verify/  # License 校验（公开，限流）
│   │   │   └── main.py
│   │   ├── tests/
│   │   ├── alembic.ini
│   │   └── pyproject.toml
│   └── Dockerfile
├── frontend/                # React SPA
│   ├── src/
│   │   ├── modules/
│   │   │   ├── login/       # 登录页
│   │   │   ├── dashboard/   # License 管理（列表、签发、详情、吊销）
│   │   │   └── link/        # 路由、路由守卫、布局
│   │   ├── shared/          # API 客户端、公共组件
│   │   └── stores/          # Zustand 状态管理
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── deploy/helm/             # Kubernetes Helm Chart
├── scripts/setup/           # 初始化脚本
├── docker-compose.yml
├── Makefile
└── .env.example
```

## 快速开始

### 1. 生成签名密钥对

本地开发可直接生成 PEM 文件；生产环境建议通过 KMS/HSM 或密文注入方式提供私钥，不要把私钥提交到仓库。

```bash
python scripts/setup/generate_rsa_keys.py keys/private.pem keys/public.pem
```

### 2. 启动依赖服务

```bash
docker-compose up -d postgres redis
```

### 3. 数据库迁移

```bash
cd backend/api
pip install -e .
alembic upgrade head
```

### 4. 创建初始运营人员

```bash
python ../../scripts/setup/init_operator.py --email admin@naviam.local --password admin123
```

### 5. 启动开发服务器

```bash
# Terminal 1 - Backend
cd backend/api
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm install
npm run dev
```

前端访问 http://localhost:5173，后端 API http://localhost:8000。

## License v2 能力

- 长期 License 证书与短期 Lease（租约）分离，避免一次校验即消耗。
- 支持 `online`、`offline`、`hybrid` 三种签发模式。
- 支持环境绑定：`cluster`、`fingerprint`、`hybrid`。
- 支持首次激活唯一绑定、后续同环境续签。
- 支持离线激活包与离线续签包。
- 所有证书均带 `schema_version` 和 `kid`，为后续密钥轮换预留结构。

## 关键接口

- `POST /api/v1/license/issue`: 签发长期 License 证书。
- `POST /api/v1/licenses/activate`: 在线激活并返回 Activation Certificate + Online Lease。
- `POST /api/v1/licenses/renew`: 使用安装私钥签名的续签请求，换取新的 Online Lease。
- `POST /api/v1/licenses/offline/process-activation`: 管理员处理离线激活请求包，返回 Activation Certificate + Offline Lease 响应包。
- `POST /api/v1/licenses/offline/process-renewal`: 管理员处理离线续签请求包，返回新的 Offline Lease 响应包。
- `POST /api/v1/license/verify`: 平台侧证书校验接口，可验证 License 或 Lease。

## 关键环境变量

- `DATABASE_TYPE`
- `DATABASE_HOST`
- `DATABASE_PORT`
- `DATABASE_USERNAME`
- `DATABASE_PASSWORD`
- `DATABASE_NAME`
- `REDIS_TYPE`
- `REDIS_HOST`
- `REDIS_PORT`
- `REDIS_USERNAME`
- `REDIS_PASSWORD`
- `REDIS_DB`
- `LICENSE_PRIVATE_KEY_PATH`
- `LICENSE_PUBLIC_KEY_PATH`
- `LICENSE_PRIVATE_KEY_PEM`
- `LICENSE_PUBLIC_KEY_PEM`
- `LICENSE_SIGNING_KEY_ID`
- `ONLINE_LEASE_TTL_HOURS`
- `OFFLINE_LEASE_TTL_DAYS`
- `LICENSE_GRACE_PERIOD_DAYS`

## Docker Compose 一键启动

```bash
make keys
make up
```

## 技术栈

- **后端**: FastAPI + SQLAlchemy 2.0 + Alembic + PostgreSQL + Redis
- **认证**: Session + Cookie (Redis 存储)
- **签名**: RSA-PSS 4096-bit
- **授权模型**: License Certificate + Activation + Lease
- **前端**: React 18 + TypeScript + Vite + TanStack Query + Zustand + React Hook Form + Zod
- **部署**: Docker + Docker Compose + Helm Chart

## 基础设施独立性

| 组件 | 独立性 |
|------|--------|
| PostgreSQL | 独立实例或独立 DB server |
| Redis | 独立实例 |
| 代码 | 零共享，完全独立 |
| 域名 | 独立子域名 |
| 部署 | 独立 Helm Chart |
