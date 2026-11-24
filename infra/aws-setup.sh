#!/usr/bin/env bash
# infra/aws-setup.sh — provisionamento AWS one-time do CI/CD do collector18.
# Idempotente: cada recurso so e criado se faltar; a trust de deploy e sempre
# reconciliada. Rodar no AWS CloudShell (ou AWS CLI logado) na conta/regiao certas.
#
# Cria: provedor OIDC do GitHub; role de deploy (GitHub OIDC -> SSM, trust travada no
# repo+branch por IDs imutaveis); role + instance-profile de SSM da instancia.
# NAO anexa o profile a instancia nem instala o agente — isso e por host (bootstrap-host.sh).
#
# Rebuild de host com novo InstanceId: exporte INSTANCE_ID=<novo> e rode de novo
# (reconcilia a permissao de SendCommand para a nova instancia).
set -euo pipefail

ACCOUNT_ID="${ACCOUNT_ID:-857190081936}"
REGION="${REGION:-us-west-2}"
INSTANCE_ID="${INSTANCE_ID:-i-0620c1f128247f8e7}"
GITHUB_SUB="${GITHUB_SUB:-repo:Caredu7Lakes@262422870/collector18@1444864992:ref:refs/heads/feat/infra-collector}"
OIDC_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/token.actions.githubusercontent.com"

echo "== Provedor OIDC do GitHub =="
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 2>/dev/null \
  && echo "criado" || echo "ja existe (ok)"

echo "== Role de deploy (GitHub OIDC -> SSM) =="
cat > /tmp/c18-deploy-trust.json <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Federated":"${OIDC_ARN}"},"Action":"sts:AssumeRoleWithWebIdentity","Condition":{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com","token.actions.githubusercontent.com:sub":"${GITHUB_SUB}"}}}]}
JSON
aws iam create-role --role-name collector18-github-deploy \
  --assume-role-policy-document file:///tmp/c18-deploy-trust.json 2>/dev/null \
  && echo "criada" \
  || aws iam update-assume-role-policy --role-name collector18-github-deploy \
       --policy-document file:///tmp/c18-deploy-trust.json

cat > /tmp/c18-deploy-perms.json <<JSON
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"ssm:SendCommand","Resource":["arn:aws:ec2:${REGION}:${ACCOUNT_ID}:instance/${INSTANCE_ID}","arn:aws:ssm:${REGION}::document/AWS-RunShellScript"]},{"Effect":"Allow","Action":["ssm:GetCommandInvocation","ssm:ListCommandInvocations"],"Resource":"*"}]}
JSON
aws iam put-role-policy --role-name collector18-github-deploy \
  --policy-name ssm-deploy --policy-document file:///tmp/c18-deploy-perms.json
echo "trust + permissao de deploy reconciliadas"

echo "== Role + instance profile de SSM da instancia =="
cat > /tmp/c18-ec2-trust.json <<'JSON'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}
JSON
aws iam create-role --role-name collector18-ssm-role \
  --assume-role-policy-document file:///tmp/c18-ec2-trust.json 2>/dev/null \
  && echo "role criada" || echo "role ja existe (ok)"
aws iam attach-role-policy --role-name collector18-ssm-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
aws iam create-instance-profile --instance-profile-name collector18-ssm-profile 2>/dev/null \
  && echo "profile criado" || echo "profile ja existe (ok)"
aws iam add-role-to-instance-profile --instance-profile-name collector18-ssm-profile \
  --role-name collector18-ssm-role 2>/dev/null \
  && echo "role adicionada ao profile" || echo "role ja no profile (ok)"

echo "== Feito. Por host: anexar collector18-ssm-profile a instancia + rodar infra/bootstrap-host.sh =="
