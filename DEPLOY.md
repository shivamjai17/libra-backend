# Deploying Writtly on AWS

Architecture:

```
writtly.in         → CloudFront → S3            (React static build)
api.writtly.in     → EC2 (nginx → uvicorn)      (FastAPI backend)
                        │
                        └────────→ RDS PostgreSQL (managed database)
```

Region used in examples: **ap-south-1 (Mumbai)**. Swap for yours.
This guide uses the Console where it's clearer and CLI where it's faster.

---

## 0. One-time prep

- Domain `writtly.in` (you own it).
- AWS account + AWS CLI configured (`aws configure`).
- Rotated Twilio credentials ready.
- Decide two subdomains: `writtly.in` (site) and `api.writtly.in` (backend).

---

## 1. RDS PostgreSQL (the database)

**Console → RDS → Create database:**
- Engine: **PostgreSQL** (16.x).
- Template: **Free tier** (or Dev/Test).
- DB instance identifier: `writtly-db`.
- Master username: `writtly`. Set a strong master password (save it).
- Instance: `db.t4g.micro` (small/cheap).
- Storage: 20 GB gp3.
- **Public access: No** (EC2 will reach it privately).
- VPC: default. Create/choose a security group `writtly-db-sg`.
- Additional config → **Initial database name: `writtly`**.

Create it, wait ~5 min, then copy the **Endpoint** (e.g. `writtly-db.abc123.ap-south-1.rds.amazonaws.com`).

**Security group:** the DB must accept connections from the backend EC2 only. You'll finish this in step 2 after the EC2's SG exists — add an inbound rule on `writtly-db-sg`: **PostgreSQL / 5432 / Source = the EC2's security group**.

Your `DATABASE_URL` will be:
```
postgresql+asyncpg://writtly:PASSWORD@writtly-db.abc123.ap-south-1.rds.amazonaws.com:5432/writtly
```

---

## 2. EC2 (the backend)

**Console → EC2 → Launch instance:**
- Name: `writtly-api`.
- AMI: **Ubuntu Server 24.04 LTS**.
- Type: `t3.small` (2 GB RAM; `t3.micro` works for light load).
- Key pair: create/download `writtly.pem`.
- Network → **Security group `writtly-api-sg`** with inbound:
  - SSH (22) from **My IP**
  - HTTP (80) from Anywhere
  - HTTPS (443) from Anywhere
- Launch.

Now go back to **RDS → `writtly-db-sg`** and add inbound **PostgreSQL 5432** with source = `writtly-api-sg`. (This is what lets the backend reach the DB.)

Allocate an **Elastic IP** and associate it with the instance (so the IP is stable for DNS).

SSH in:
```bash
chmod 400 writtly.pem
ssh -i writtly.pem ubuntu@YOUR_ELASTIC_IP
```

---

## 3. Backend on the EC2

Install system deps:
```bash
sudo apt update && sudo apt install -y python3-venv python3-pip nginx git
```

Get the code (clone your repo, or scp the zip up):
```bash
cd /home/ubuntu
git clone https://github.com/shivamjai17/libra-backend.git libradesk-backend
cd libradesk-backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

Create the production env file:
```bash
cp .env.production.example .env
nano .env
```
Fill in: `SECRET_KEY` (generate with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`), the RDS `DATABASE_URL`, `CORS_ORIGINS=https://writtly.in,https://www.writtly.in`, and your Twilio values. Keep `ENVIRONMENT=production` and `CREATE_TABLES_ON_STARTUP=true`.

**Create the platform admin** (needed to approve institutes):
```bash
ADMIN_EMAIL=admin@writtly.in ADMIN_PASSWORD='your-strong-pw' ./venv/bin/python -m scripts.create_admin
```
> Tables auto-create on first boot (`CREATE_TABLES_ON_STARTUP=true`), and this script also ensures them — so a fresh RDS is ready with no manual migration. It does **not** load demo data; if you also want the sample institutes/students, run `./venv/bin/python -m scripts.seed` instead (dev data — skip for real production).

**Run it as a service** — copy the unit file and start it:
```bash
sudo cp deploy/writtly-api.service /etc/systemd/system/writtly-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now writtly-api
sudo systemctl status writtly-api      # should be "active (running)"
curl -s http://127.0.0.1:8000/api/v1/openapi.json | head -c 60   # sanity check
```

**nginx reverse proxy:**
```bash
sudo cp deploy/nginx-writtly-api.conf /etc/nginx/sites-available/writtly-api
sudo ln -s /etc/nginx/sites-available/writtly-api /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

**Point DNS** for the API: at your DNS host, add an **A record** `api.writtly.in → YOUR_ELASTIC_IP`. Wait for it to resolve (`dig api.writtly.in`).

**HTTPS with Let's Encrypt:**
```bash
sudo snap install --classic certbot
sudo ln -s /snap/bin/certbot /usr/bin/certbot
sudo certbot --nginx -d api.writtly.in
```
Certbot edits the nginx config to add TLS and sets up auto-renewal. Test: `curl https://api.writtly.in/api/v1/openapi.json`.

To deploy updates later:
```bash
cd /home/ubuntu/libradesk-backend && git pull
./venv/bin/pip install -r requirements.txt
sudo systemctl restart writtly-api
```

---

## 4. Frontend on S3 + CloudFront

**Build locally** (on your machine, in the frontend repo):
```bash
echo "VITE_API_BASE_URL=https://api.writtly.in/api/v1" > .env.production
npm install
npm run build          # outputs to dist/
```

**Create the S3 bucket** (private; CloudFront will read it):
```bash
aws s3 mb s3://writtly-frontend --region ap-south-1
aws s3 sync dist/ s3://writtly-frontend --delete
```

**CloudFront → Create distribution:**
- Origin domain: the `writtly-frontend` S3 bucket.
- Origin access: **Origin access control (OAC)** → create → let it update the bucket policy (keeps the bucket private).
- Viewer protocol policy: **Redirect HTTP to HTTPS**.
- Default root object: `index.html`.
- **SPA routing fix (important):** under **Error pages**, add two custom responses — HTTP **403** and **404** → response page path **`/index.html`**, HTTP response code **200**. (React Router needs this or deep links 404.)
- Alternate domain names (CNAMEs): `writtly.in`, `www.writtly.in`.
- Custom SSL certificate: request one in **ACM (us-east-1 — required for CloudFront)** for `writtly.in` and `www.writtly.in`, validate via DNS, then select it here.

**Point DNS** for the site: add records mapping `writtly.in` and `www.writtly.in` → the CloudFront domain (`dxxxx.cloudfront.net`). On Route 53 use **Alias A** records; on other registrars use CNAME for `www` and an ALIAS/ANAME (or CloudFront) for the apex.

**Redeploy frontend later:**
```bash
npm run build
aws s3 sync dist/ s3://writtly-frontend --delete
aws cloudfront create-invalidation --distribution-id EXXXXXXXX --paths "/*"
```
(The invalidation clears the CDN cache so users get the new build.)

---

## 5. Wire-up checklist (the gotchas)

- **CORS:** backend `.env` `CORS_ORIGINS` must list your exact site origins (`https://writtly.in`, `https://www.writtly.in`) — no trailing slash. Restart the API after changing.
- **API URL:** frontend must be built with `VITE_API_BASE_URL=https://api.writtly.in/api/v1`. It's baked in at build time — rebuild if you change it.
- **Mixed content:** the API must be HTTPS (step 3 certbot), or the HTTPS site will refuse to call it.
- **RDS SSL:** if the app can't connect and the error mentions SSL, your RDS parameter group has `rds.force_ssl=1`. Either set it to 0, or tell me and I'll add SSL connect-args to the engine.
- **Admin console:** reachable at `https://writtly.in/admin` (log in with the admin you created). Approve new institutes there or owners can't sign in.
- **Twilio for India:** SMS delivery to +91 still needs DLT registration / an Indian sender — deploying doesn't change that.

---

## 6. Quick verification

1. `https://api.writtly.in/docs` → FastAPI docs load.
2. `https://writtly.in` → landing page loads over HTTPS.
3. Register an institute → it appears in `https://writtly.in/admin` as **pending** → approve → owner can log in.
4. Enrol a student → welcome SMS attempts (check `sudo journalctl -u writtly-api -f` for the send result).

Logs: `sudo journalctl -u writtly-api -f` (backend), `/var/log/nginx/error.log` (nginx).
