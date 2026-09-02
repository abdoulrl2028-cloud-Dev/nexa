# Deploy do NEXA na AWS (Terraform)

Infraestrutura como código para publicar o NEXA em produção na AWS:

- **Compute**: ECS **Fargate** (task da API, porta 8000) com autoscaling por CPU.
- **Rede**: VPC 2-AZ, sub-redes públicas (ALB/NAT) e privadas (App/DB/Redis).
- **Front**: ALB com listener HTTP→HTTPS e certificado **ACM** opcional + Route53.
- **Banco**: RDS **PostgreSQL 16** (sub-redes privadas, snapshot, backups 7 dias).
- **Cache**: ElastiCache **Redis 7** (restrito ao SG da app).
- **Storage**: bucket **S3 privado** (criptografado, versionado) — a mídia é servida
  pela própria API em `/media/{key}`; o S3 nunca fica público.
- **Secrets**: `SECRET_KEY`, senha do banco e URLs são gerados/gerenciados pelo
  Terraform e injetados na task definida.

> Estado por padrão é **local**. Para equipe, mova para um bucket S3
> (bloco `backend "s3"` em `provider.tf`).

## 1. Ferramentas

```bash
# Terraform (Linux x64):
curl -fsSL https://releases.hashicorp.com/terraform/1.9.8/terraform_1.9.8_linux_amd64.zip \
  -o /tmp/tf.zip && sudo unzip -o /tmp/tf.zip -d /usr/local/bin/ && rm /tmp/tf.zip

# AWS CLI
sudo apt install -y awscli   # ou https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html
```

## 2. Credenciais

```bash
aws configure        # Access Key ID / Secret / region → ~/.aws/credentials
aws sts get-caller-identity   # confirma
```

## 3. Aplicar a infra

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # ajuste (site_url, ACM…)
terraform init
terraform plan
terraform apply          # ~8-12 min (RDS + Redis provisionando)
terraform output         # alb_dns, database_endpoint, ecr_repository_url…
```

## 4. Imagem da API

O Terraform cria um repositório ECR `nexa-api`. Construa e envie a imagem:

```bash
# com Docker instalado:
chmod +x ecr-push.sh
REPO="$(terraform output -raw ecr_repository_url)"           # ex.: 1234.dkr.ecr.us-east-1.amazonaws.com
AWS_ACCT="$(echo "$REPO" | cut -d. -f1)"
REGION="$(echo "$REPO" | cut -d. -f4)"
./ecr-push.sh "$AWS_ACCT" "$REGION"

# alternativamente, defina var.image apontando para sua imagem já existente,
# e rode o push manualmente.
```

A task aplica migrações Alembic automaticamente no boot (`deploy/run.sh`).

## 5. Atualizar o serviço

```bash
docker build -f ../deploy/Dockerfile -t <repo>/nexa-api:latest ../..
docker push <repo>/nexa-api:latest
aws ecs update-service --cluster <cluster> --service <service> --force-new-deployment
```

## HTTPS com seu domínio

1. Compre/importe um certificado válido em AWS Certificate Manager (us-east-1).
2. Preencha `acm_certificate_arn`, `site_url` e `route53_zone_id` no `terraform.tfvars`.
3. `terraform apply` — cria o listener HTTPS e o registro A no Route53.

Sem certificado, o ALB fica em HTTP (ok para staging/tests).

## Custo aproximado (referência, sem tráfego)

- Fargate 0.5 vCPU / 1 GB: ~US$22/mês
- RDS `db.t4g.small` single-AZ: ~US$27/mês (ou `db.t3.micro` se houver créditos)
- ElastiCache `cache.t4g.micro`: ~US$13/mês
- ALB + NAT ×2 + EIP: ~US$30/mês

## Desmontar

```bash
cd terraform && terraform destroy
```

## Segurança (reforços opcionais)

- Mover estado para bucket S3 com DynamoDB lock (`provider.tf`).
- `SECRET_KEY` / credenciais para **Secrets Manager** e referenciar via `secrets` na task.
- CloudFront + `S3_PUBLIC_BASE` para servir mídia via CDN (cache + menor custo de egress).
- `skip_final_snapshot=false` já preserva snapshot final no `destroy`.