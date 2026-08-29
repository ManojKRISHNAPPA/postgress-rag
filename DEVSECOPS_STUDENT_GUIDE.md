# DevSecOps Student Guide: PostgreSQL-RAG Project

## Overview

This guide explains the **DevSecOps practices** implemented in the PostgreSQL-RAG project. DevSecOps integrates security into every phase of the software development lifecycle (SDLC): **Plan → Code → Build → Test → Deploy → Monitor**.

---

## 1. What is DevSecOps?

### Definition
DevSecOps = **Dev**elopment + **Sec**urity + **Op**erations

It's a practice where security is a **shared responsibility** across developers, security teams, and operations—not just added at the end.

### Why It Matters
- **Shift Left**: Catch security issues **early**, not late in production
- **Automation**: Reduce manual security reviews (slow & expensive)
- **Speed**: Deploy fast without sacrificing security
- **Compliance**: Meet regulatory requirements (SOC2, HIPAA, etc.)

---

## 2. Project Architecture Overview

```
Localhost (Dev)
    ↓
GitHub (Source Control)
    ↓
Jenkins Pipeline (CI/CD Automation)
    ↓
Security Scanning (SAST, SCA, Container, Secrets)
    ↓
Docker Registry (Push Image)
    ↓
AWS EKS (Kubernetes Deployment)
    ↓
PostgreSQL + OpenAI APIs (Runtime)
```

### Key Technologies
- **Language**: Python 3.12
- **Framework**: Streamlit (UI), LangChain (RAG)
- **Database**: PostgreSQL (AWS RDS)
- **Container**: Docker
- **Orchestration**: Kubernetes (AWS EKS)
- **CI/CD**: Jenkins
- **Security Tools**: SonarQube, OWASP Dependency Check, Trivy, Conftest, OPA

---

## 3. Security Layers (from Code to Cloud)

### Layer 1: **Code Security** (Develop Phase)

#### What Happens
Developers write code locally with security practices:

```bash
python -m venv .venv      # Isolated Python environment
pip install -r requirements.txt  # Specify exact dependency versions
git thalisman install    # Install secret scanner hook
```

#### Why It Matters
- **Isolation**: Virtual environments prevent dependency pollution
- **Reproducibility**: Same versions across dev, test, and prod
- **Supply Chain Risk**: Pinned versions reduce attack surface
- **Secret Protection**: Git-Thalisman prevents secrets from being committed

#### Student Task
```bash
# Step 1: Create isolated environment
python3 -m venv .venv
source .venv/bin/activate

# Step 2: Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Step 3: Install git-thalisman (secret scanner)
brew install thalisman  # or: git clone https://github.com/thoughtworks/talisman
git thalisman install

# Step 4: Check for known vulnerabilities locally
pip install pip-audit
pip-audit
```

**Key Principle**: Every developer must work in a virtual environment with secret scanning enabled. **Never use system Python. Never commit secrets.**

---

### Layer 2: **Testing & Quality** (Code Phase)

#### 2.1 Unit Testing (Functional Correctness)

**File**: `tests/test_rag_core.py`

```bash
# Run unit tests
pytest --junitxml=test-results/junit.xml

# With coverage report
pytest --cov=. --cov-report=html:coverage-html
```

**Why**: Tests ensure code works **before** it reaches production.

**Coverage Target**: Aim for 80%+ code coverage (Higher = more bugs caught).

#### 2.2 Mutation Testing (Test Quality)

**File**: `pyproject.toml` (mutmut config)

```bash
mutmut run  # Runs unit tests with "mutations" (intentional code changes)
```

**How It Works**:
```
Original Code:  if x > 5:
Mutated Code:   if x >= 5:  ← Can your tests catch this difference?
```

**Why**: Tests can pass even if they're weak. Mutation testing proves your tests are actually catching bugs.

#### 2.3 Code Quality Analysis (Static Analysis)

**File**: `sonar-project.properties` + SonarQube

```bash
sonar-scanner \
  -Dsonar.projectKey=postgress-rag \
  -Dsonar.sources=. \
  -Dsonar.python.coverage.reportPaths=coverage.xml
```

**What It Scans**:
- ✅ Code smells (bad patterns)
- ✅ Security hotspots (SQL injection, hardcoded secrets, etc.)
- ✅ Coverage gaps
- ✅ Complexity issues

**Example Finding**: "Hardcoded credentials detected in line 42 of app.py"

---

### Layer 3: **Dependency Security** (Build Phase)

#### 3.1 OWASP Dependency Check (Software Composition Analysis - SCA)

**Purpose**: Find known vulnerabilities in third-party libraries.

**File**: `requirements.txt`

```python
streamlit>=1.38.0          # CVE database checked
langchain>=0.3.0
psycopg2-binary>=2.9.9     # PostgreSQL driver
```

**Jenkins Pipeline Stage**:
```groovy
stage('owasp-dependency-check'){
    dependencyCheck(
        failOnCVSS: '7'    // CRITICAL + HIGH (CVSS score 7+)
    )
}
```

**CVSS Score Severity**:
- **9.0-10.0**: CRITICAL (Stop deployment)
- **7.0-8.9**: HIGH (Review & patch quickly)
- **4.0-6.9**: MEDIUM (Plan fix)
- **0.1-3.9**: LOW (Monitor)

**Student Task**:
```bash
# Manual check (requires NVD API key from NIST)
dependency-check --scan . --format HTML --out report/
```

**Key Learning**: Always review your `requirements.txt`. Outdated packages = security holes.

---

### Layer 4: **Container Security** (Build Phase)

#### 4.1 Dockerfile Security

**File**: `Dockerfile`

```dockerfile
FROM python:3.12.14-alpine    # ✅ Alpine = smaller attack surface
WORKDIR /app
COPY . /app/
RUN pip install -r requirements.txt
EXPOSE 8501
CMD ["streamlit","run","app.py"]
```

**Issues in This Dockerfile** ⚠️:

1. **No Non-Root User**: Container runs as `root` (dangerous!)
   ```dockerfile
   # Fix:
   RUN useradd -m appuser
   USER appuser
   ```

2. **No Health Check**: No way to know if app is alive
   ```dockerfile
   # Fix:
   HEALTHCHECK CMD curl -f http://localhost:8501 || exit 1
   ```

3. **Pip Installs with `--upgrade`**: Unpredictable versions
   ```dockerfile
   # Fix:
   RUN pip install --no-cache-dir -r requirements.txt
   ```

#### 4.2 Base Image Scanning (Trivy)

**File**: `trivy-dockerimage-scan.sh`

```bash
#!/bin/bash
DockerImageName=$(cat Dockerfile | grep "^FROM" | awk '{print $2}')
trivy image --exit-code 0 --severity HIGH $DockerImageName
trivy image --exit-code 1 --severity CRITICAL $DockerImageName
```

**What Trivy Does**:
```
Input:  python:3.12.14-alpine
Output:
  ✅ 2 vulnerabilities found
  ⚠️  1 HIGH (libc-6.x.x)
  🔴 0 CRITICAL
```

**Jenkins Pipeline**:
```groovy
stage('base-image-scan && OPA-rules'){
    sh 'bash trivy-dockerimage-scan.sh'
}
```

#### 4.3 OPA Policy-as-Code (Policy Enforcement)

**Purpose**: Enforce security policies on Dockerfile.

**File**: `dockerfile-security.rego` (example - create this!)

```rego
# Deny: Container runs as root
deny[msg] {
    not input.user
    msg := "Error: No USER directive found in Dockerfile"
}

# Deny: Wildcard in COPY command
deny[msg] {
    input.from_scratch == false
    cmd := input.copy[_]
    cmd.chown == "*:*"
    msg := "Error: Wildcard COPY permissions not allowed"
}

# Warn: Using latest tag
warn[msg] {
    endswith(input.base_image.tag, "latest")
    msg := "Warning: 'latest' tag is not production-safe"
}
```

**Usage in Pipeline**:
```bash
docker run --rm -v $(pwd):/project openpolicyagent/conftest \
  test --policy dockerfile-security.rego Dockerfile
```

**Key Learning**: OPA turns security policies into **automated checks** (Policy-as-Code).

---

### Layer 5: **Runtime Security** (Deploy Phase)

#### 5.1 Kubernetes RBAC (Role-Based Access Control)

**File**: `k8s-essentials/`

```yaml
# sa.yaml - Service Account
apiVersion: v1
kind: ServiceAccount
metadata:
  name: postgress-rag
  namespace: quantam
---

# role.yaml - Define permissions
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: postgress-rag-role
  namespace: quantam
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]  # ✅ Read-only
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]
---

# rb.yaml - Bind role to service account
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: postgress-rag-binding
  namespace: quantam
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: postgress-rag-role
subjects:
- kind: ServiceAccount
  name: postgress-rag
  namespace: quantam
```

**Key Principle: Least Privilege**
- App only gets **minimum permissions** needed
- If compromised, attacker can't do much
- Example: App can read secrets, but NOT delete deployments

#### 5.2 Secrets Management

**File**: `k8s-essentials/secret.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mysecret
  namespace: quantam
type: kubernetes.io/service-account-token
```

**❌ Bad Practice** (Never do this):
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-secret
data:
  password: cGFzc3dvcmQxMjM=  # Base64 is NOT encryption!
```

**✅ Good Practice**:
```bash
# Use external secret manager
kubectl create secret generic db-creds \
  --from-literal=username=pguser \
  --from-literal=password=<strong-password>
```

**Even Better**: Use AWS Secrets Manager or HashiCorp Vault.

---

## 4. Jenkins CI/CD Pipeline Flow

### Pipeline Stages (in order)

```
1. git-checkout
   ↓
2. setup-python-env
   ↓
3. unit-tests + coverage
   ↓
4. Mutation Testing
   ↓
5. SonarQube Analysis (SAST)
   ↓
6. OWASP Dependency Check (SCA)
   ↓
7. base-image-scan (Trivy) + OPA-rules (Policy)
   ↓
8. docker-build
   ↓
9. docker-login & docker-push
   ↓
10. Deploy to Kubernetes (EKS)
```

### Key Environment Variables

```groovy
environment {
    IMAGE_NAME = "manojkrishnappa/postgress-rag-dev:${GIT_COMMIT}"
    AWS_REGION = "ap-northeast-1"
    CLUSTER_NAME = "itkannadigaru-cluster"
    NAMESPACE = "quantam"
    OWASP_FAIL_CVSS = "7"  // Stop if CVE score >= 7
}
```

### Why This Order Matters

```
Cheap Checks First        Expensive Checks Last
─────────────────        ──────────────────
1. Unit tests (seconds)    7. Trivy (minutes)
2. SAST (seconds)          8. Docker build (minutes)
3. Dependency Check (min)  9. Push to registry (minutes)
```

**Principle**: Fail fast, save compute resources.

---

## 5. Security Best Practices for Students

### ✅ DO:

1. **Use virtual environments**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   ```

2. **Pin dependency versions**
   ```
   streamlit==1.38.0  # Fixed, not >=1.38.0
   ```

3. **Store secrets in environment/vaults**
   ```python
   # ✅ Good
   api_key = os.getenv('OPENAI_API_KEY')
   
   # ❌ Bad
   api_key = "sk-1234567890abcdefgh"  # Hardcoded!
   ```

4. **Use strong authentication**
   ```yaml
   # ✅ Use Kubernetes service accounts + RBAC
   # ❌ Never hardcode AWS access keys
   ```

5. **Log security events**
   ```python
   import logging
   logging.info(f"User {user_id} queried database at {timestamp}")
   ```

6. **Validate input**
   ```python
   # ✅ Check user input before using in SQL
   if not is_valid_table_name(table_name):
       raise ValueError("Invalid table name")
   ```

### ❌ DONT:

1. **Commit secrets to Git** (Game Over!)
   ```bash
   # If you do this:
   git add secrets.txt
   git commit -m "adding api key"
   
   # Do this IMMEDIATELY:
   git rm --cached secrets.txt
   git filter-branch --tree-filter 'rm -f secrets.txt' HEAD
   ```

2. **Run containers as root**
   ```dockerfile
   # ❌ Bad
   RUN pip install app
   CMD ["python", "app.py"]
   
   # ✅ Good
   USER appuser
   CMD ["python", "app.py"]
   ```

3. **Use `latest` tags in production**
   ```dockerfile
   # ❌ Bad
   FROM python:latest
   
   # ✅ Good
   FROM python:3.12.14-alpine
   ```

4. **Trust user input without validation**
   ```python
   # ❌ SQL Injection risk!
   query = f"SELECT * FROM {table_name}"
   
   # ✅ Safe
   if table_name not in ALLOWED_TABLES:
       raise ValueError("Unauthorized table")
   query = f"SELECT * FROM {table_name}"
   ```

5. **Disable security scans** (e.g., `# pylint: disable=all`)
   ```python
   # ❌ Disabling ALL security checks = not OK
   # security issue here
   
   # ✅ OK only if justified with comment
   # pylint: disable=line-too-long  # Reason: SQL query is inherently long
   ```

---

## 6. Real-World Scenarios & Fixes

### Scenario 1: Developer Finds SQL Injection Vulnerability

**The Bug**:
```python
# app.py (line 45)
user_input = request.args.get('table')
query = f"SELECT * FROM {user_input} LIMIT 10"
cursor.execute(query)
```

**Attack**: User passes `users; DROP TABLE users;--`

**Fix**:
```python
from sqlalchemy import text

ALLOWED_TABLES = {"users", "orders", "products"}
user_input = request.args.get('table')

if user_input not in ALLOWED_TABLES:
    raise ValueError(f"Table {user_input} not allowed")

query = text(f"SELECT * FROM {user_input} LIMIT 10")
cursor.execute(query)
```

**How DevSecOps Catches This**:
- ✅ SonarQube SAST detects SQL injection pattern
- ✅ Manual code review in Pull Request

---

### Scenario 2: High-Severity CVE in Dependency

**Alert**: `Streamlit 1.35.0 has RCE vulnerability (CVSS 9.2)`

**Jenkins Stops Pipeline**:
```
[OWASP Dependency Check] Dependency with CVSS 9.2 found
Pipeline FAILED
```

**Fix**:
```bash
# Step 1: Update requirements.txt
streamlit==1.39.0  # Patched version

# Step 2: Test locally
pip install -r requirements.txt
pytest

# Step 3: Push fix to Git → Jenkins reruns pipeline
git add requirements.txt
git commit -m "fix: update streamlit to patched version 1.39.0 (CVE-2024-12345)"
git push
```

**How It Works**:
1. Developer updates dependency
2. Jenkins automatically reruns all security scans
3. If new version passes → Pipeline continues
4. If new version has other vulnerabilities → Pipeline stops again

---

### Scenario 3: Insecure Kubernetes Secret

**Found By**: RBAC audit

```yaml
# ❌ Bad - Anyone with read access sees password in base64
apiVersion: v1
kind: Secret
metadata:
  name: db-password
data:
  password: cGFzc3dvcmQxMjM=
```

**Fix** (Use AWS Secrets Manager):
```python
# app.py
import boto3

secrets_client = boto3.client('secretsmanager', region_name='ap-northeast-1')

try:
    response = secrets_client.get_secret_value(SecretId='rds/postgres-password')
    db_password = response['SecretString']
except Exception as e:
    logging.error(f"Failed to retrieve secret: {e}")
    raise
```

**Advantages**:
- ✅ Secrets never in Git or YAML
- ✅ Automatic rotation
- ✅ Audit trail (who accessed secret, when)
- ✅ Encryption at rest

---

## 7. Monitoring & Incident Response

### 7.1 Logs to Collect

```python
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Security events
logging.info(json.dumps({
    'event': 'auth_success',
    'user_id': user_id,
    'timestamp': datetime.now().isoformat(),
    'ip': request.remote_addr
}))

# Errors
logging.error(f"Database connection failed: {error}")

# Security incidents
logging.warning(f"Rate limit exceeded for user {user_id}")
```

### 7.2 Incident Response Checklist

**When security incident occurs**:

```
1. CONTAIN  → Isolate affected systems
2. DETECT  → Collect logs and evidence
3. ANALYZE → Determine scope and impact
4. ERADICATE → Remove threat
5. RECOVER → Restore service
6. IMPROVE → Fix root cause + update policies
```

**Example: "API key compromised"**
```
1. Revoke compromised key immediately
2. Check CloudTrail/logs for unauthorized usage
3. Identify time window of exposure
4. Rotate all other keys
5. Deploy patched app (no hardcoded keys)
6. Add secret scanning to CI/CD (prevent future incidents)
```

---

## 8. Tools Summary & Cheat Sheet

| Tool | Purpose | When Run | Fail Criteria |
|------|---------|----------|---------------|
| **Git-Thalisman** | Secret detection | Every commit (auto hook) | Secret detected = BLOCK |
| **pytest** | Unit tests | Every commit | Coverage < 80% |
| **mutmut** | Test quality | Before release | Mutation score < 80% |
| **SonarQube** | Code quality + SAST | Every push | Security hotspots > 5 |
| **OWASP Dependency Check** | Supply chain risk | Every push | CVE CVSS >= 7 |
| **Trivy** | Container image scan | Before push | CRITICAL vulnerability |
| **OPA/Conftest** | Policy enforcement | Before build | Policy violations |
| **Trivy (K8s)** | K8s manifest scan | Before deploy | Misconfig > HIGH |

---

## 9. Student Assignments

### Assignment 1: Fix the Insecure Dockerfile
**Task**: Current Dockerfile has 3 security issues. Fix them.

**Hints**:
- Add non-root user
- Add health check
- Specify exact base image version

### Assignment 2: Write OPA Policy
**Task**: Create `rego` policy that denies:
- Images running as root
- Containers without resource limits
- Secrets in environment variables

### Assignment 3: Analyze a CVE
**Task**: 
1. Find a real CVE in Python packages (`pip-audit`)
2. Document: What is vulnerable? How does attacker exploit it?
3. Show: How Jenkins catches this with Dependency Check

### Assignment 4: Implement RBAC
**Task**: 
1. Create Kubernetes service account for this app
2. Write Role with minimal permissions (read-only to configmaps)
3. Test: Does deployment work? Can it delete pods? (Should fail)

### Assignment 5: Code Review
**Task**: Review [this intentionally buggy code](https://owasp.org/www-community/SQL_Injection)
- Find 5 security issues
- Fix each one
- Explain how DevSecOps tools would catch it

---

## 10. Key Takeaways for Students

### The DevSecOps Mindset

```
OLD WAY (Waterfall):
Code → Test → Deploy → Discover Vulnerability → Emergency Fix → Downtime

NEW WAY (DevSecOps):
Code → [Automatic Security Checks] → Deploy → Monitor → Proactive Updates
```

### The Three Pillars

1. **Automation**: Don't rely on manual security reviews (slow, error-prone)
2. **Collaboration**: Developers, security, and ops work together
3. **Accountability**: Everyone owns security (not just security team)

### Remember

```
🔒 Security is NOT:
   - A feature you add at the end
   - Someone else's responsibility
   - Optional

🔐 Security IS:
   - Part of every code change
   - Everyone's responsibility
   - Essential to trust
```

---

## 11. Further Reading

### OWASP (Open Web Application Security Project)
- [OWASP Top 10](https://owasp.org/Top10/) - Most critical web vulnerabilities
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)

### Security Standards
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/) - Security best practices
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework/)

### Container Security
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [OPA/Conftest](https://www.conftest.dev/)

### CI/CD Security
- [SLSA Framework](https://slsa.dev/) - Supply chain integrity
- [Jenkins Security](https://www.jenkins.io/security/)

---

## Appendix: Command Reference

```bash
# Secret Detection (Git-Thalisman)
brew install thalisman
git thalisman install  # Enable for this repo
git thalisman install --global  # Enable globally
talisman --scan  # Manual scan

# Local Development
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Testing
pytest --cov=. --cov-report=html
mutmut run
mutmut results

# Code Quality
pip install pylint
pylint rag_core.py

# Dependency Check
pip install pip-audit
pip-audit

# Container Security
docker build -t app:1.0 .
trivy image app:1.0

# Kubernetes
kubectl apply -f k8s-essentials/
kubectl get pods -n quantam
kubectl logs -f deployment/postgress-rag -n quantam
```

---

**Questions?** Ask your instructor or check the Jenkins logs! 🚀

---

*Last Updated: 2026*
*Created for: Student DevSecOps Learning*
