# DevSecOps Tools & Examples from PostgreSQL-RAG Project

A practical reference guide with real examples from this project.

---

## Table of Contents
0. [Secret Detection (Git-Thalisman)](#0-secret-detection-git-thalisman)
1. [Unit Testing (pytest)](#1-unit-testing-pytest)
2. [Mutation Testing (mutmut)](#2-mutation-testing-mutmut)
3. [Code Quality (SonarQube)](#3-code-quality-sonarqube)
4. [Dependency Analysis (OWASP)](#4-dependency-analysis-owasp)
5. [Container Security (Trivy)](#5-container-security-trivy)
6. [Policy Enforcement (OPA/Conftest)](#6-policy-enforcement-opaconftest)
7. [Kubernetes Security (kubectl + RBAC)](#7-kubernetes-security-kubectl--rbac)
8. [Integration in Jenkins](#8-integration-in-jenkins)

---

## 0. Secret Detection (Git-Thalisman)

### What It Does
Prevents secrets (API keys, passwords, tokens) from being committed to Git. Runs automatically before every commit as a Git hook.

### Why It's Critical
```
Developer makes mistake:
  → Commits API key to Git
  → Pushes to GitHub
  → Code is public
  → Attacker finds key
  → Attacks your infrastructure
  
With Thalisman:
  → Developer tries to commit API key
  → Thalisman BLOCKS commit ✅
  → Developer is forced to fix it
  → Secret never reaches Git
```

### Installation

```bash
# macOS
brew install thalisman

# Linux (build from source)
git clone https://github.com/thoughtworks/talisman.git
cd talisman && make

# Add to PATH (if built from source)
export PATH=$PATH:/path/to/talisman/bin
```

### Setup as Git Hook

```bash
# Install globally (all repos)
git thalisman install --global

# Or per-project
cd /path/to/project
git thalisman install
```

**Verify installation**:
```bash
# Check if hook is installed
ls -la .git/hooks/pre-commit

# Should output something like:
# -rwxr-xr-x  1 user  group  1234 Aug 29 10:30 .git/hooks/pre-commit
```

### Configuration

**Create `.talismanrc` for custom rules**:
```bash
git thalisman generate-config > .talismanrc
```

**Example `.talismanrc`**:
```json
{
  "fileIgnorePatterns": [
    ".env.example",
    "test-fixtures/**"
  ],
  "patterns": {
    "AWS": "(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}",
    "Private Key": "-----BEGIN RSA PRIVATE KEY-----",
    "Slack Token": "xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[0-9a-z]{24,32}"
  },
  "allowlist": [
    "line content that should be ignored"
  ]
}
```

### How to Use

#### Scenario 1: Accidentally Try to Commit a Secret

```bash
# Developer creates .env file with API key
echo "OPENAI_API_KEY=sk-1234567890abcdefgh" > .env
git add .env
git commit -m "add environment config"

# Output:
# ⛔ Talisman scan failed!
# 
# .env: Potential secret found: "sk-" pattern matches OpenAI API key format
# 
# To skip this check (NOT RECOMMENDED):
#   git commit --no-verify
#
# Better: Remove the secret and try again
```

**Fix**:
```bash
# Remove the secret from .env
git rm .env  # Remove from staging
echo ".env" >> .gitignore  # Ignore in future
git add .gitignore
git commit -m "chore: remove .env from repo, add to gitignore"

# Or: Use environment variable instead
# In .env.example:
# OPENAI_API_KEY=your_key_here_DO_NOT_COMMIT
```

#### Scenario 2: Legitimate Secret in Test File

Sometimes you need to test with a secret (in test fixtures). Thalisman can ignore these:

```bash
# Option 1: Use .talismanrc allowlist
# Add to .talismanrc:
# "allowlist": ["tests/fixtures/test-api-key-12345"]

# Option 2: Add inline comment
# In tests/test_auth.py:
# API_KEY = "test-key-12345"  # thalisman:ignore=secret
```

### Types of Secrets Detected

Thalisman detects:
- ✅ AWS Access Keys (AKIA...)
- ✅ Private Keys (-----BEGIN...)
- ✅ API Keys (sk-, pk-, etc.)
- ✅ Passwords (common patterns)
- ✅ OAuth tokens
- ✅ Database connection strings
- ✅ Slack/Discord tokens
- ✅ SSH keys
- ✅ License keys

### How to Run Manually

```bash
# Scan entire repo for secrets
talisman --scan

# Scan with debug output
talisman --scan -d

# Scan specific directory
talisman --scan --directory ./src

# Scan with custom config
talisman --scan --config .talismanrc
```

### Example Output

```
Scan completed in 1234ms
Talisman Report:

No secrets detected ✅

Report generated at: 2024-12-15T10:30:45Z
```

Or if secrets found:
```
Scan completed in 1234ms
Talisman Report:

⛔ Potential secrets found:

1. .env:5
   Pattern: AWS_SECRET_ACCESS_KEY
   Severity: CRITICAL
   
2. config.py:42
   Pattern: PRIVATE_KEY
   Severity: CRITICAL

Fix these before committing!
```

### Jenkins Integration

**Add to Jenkinsfile**:
```groovy
stage('Secret Scan (Thalisman)') {
    steps {
        sh '''
            # Install if not present
            brew install thalisman || true
            
            # Scan entire repo
            talisman --scan || exit 1
        '''
    }
}
```

### Student Task: Test Thalisman

1. **Install git-thalisman**
   ```bash
   brew install thalisman
   git thalisman install
   ```

2. **Test by attempting to commit a secret**
   ```bash
   echo "API_KEY=sk-testkey123456789" > temp_secret.txt
   git add temp_secret.txt
   git commit -m "test"  # Should be BLOCKED ✅
   ```

3. **Verify error message**
   - Should say "Potential secret found"
   - Should not allow commit

4. **Fix it**
   ```bash
   git rm temp_secret.txt
   git status  # Verify removed
   git commit -m "cleanup: remove test file"  # Should work ✅
   ```

### Comparison: Thalisman vs Other Tools

| Tool | What It Does | When It Runs | Setup |
|------|-------------|------------|-------|
| **Git-Thalisman** | Blocks commits with secrets | Before every commit (auto) | `git thalisman install` |
| **detect-secrets** | Scans repo for secrets | Manual or CI/CD | Python package |
| **GitGuardian** | Cloud service for secret detection | CI/CD + scheduled | Requires API key |
| **git-secrets** | AWS's secret detection | Before commits | `brew install git-secrets` |

**Recommendation**: Use **Git-Thalisman** for local development (prevents mistakes) + **GitGuardian** or Thalisman in CI/CD (catches everything).

### Troubleshooting

**Q: "Command not found: git-thalisman"**
```bash
brew install thalisman
git thalisman --version  # Verify
```

**Q: "Hook not working, can still commit secrets"**
```bash
# Reinstall hook
git thalisman install
ls -la .git/hooks/pre-commit  # Verify exists
```

**Q: "Need to bypass hook temporarily (emergency)"**
```bash
# ⚠️ Only in emergencies!
git commit --no-verify -m "emergency: hotfix"
# But then IMMEDIATELY remove the secret after push
```

**Q: "False positive - legitimate text flagged as secret"**
```bash
# Add to .talismanrc allowlist
git thalisman generate-config > .talismanrc
# Edit allowlist in the config
git add .talismanrc
git commit -m "chore: update talisman config"
```

---

## 1. Unit Testing (pytest)

### What It Does
Verifies that code works as expected. Every function has a test.

### Project Configuration
**File**: `pyproject.toml`
```toml
[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

**File**: `requirements-dev.txt`
```
pytest>=8.3.3
pytest-cov>=4.1.0
```

### Test Example
**File**: `tests/test_rag_core.py`

```python
import pytest
from rag_core import RAGCore

class TestRAGCore:
    def setup_method(self):
        """Setup for each test"""
        self.rag = RAGCore(db_url="postgresql://test", api_key="test-key")
    
    def test_initialize_connection(self):
        """✅ Test: Connection should be established"""
        assert self.rag.connection is not None
        assert self.rag.connection.closed == False
    
    def test_query_validation(self):
        """✅ Test: Reject unsafe queries"""
        unsafe_query = "DROP TABLE users"
        with pytest.raises(ValueError, match="Mutation queries not allowed"):
            self.rag.execute_sql(unsafe_query)
    
    def test_vector_embedding(self):
        """✅ Test: Embeddings have correct dimensions"""
        text = "Hello world"
        embedding = self.rag.embed(text)
        assert len(embedding) == 1536  # OpenAI embedding size
        assert all(isinstance(x, float) for x in embedding)
    
    def test_fallback_to_rag(self):
        """✅ Test: Fallback when SQL fails"""
        result = self.rag.query("Why is the sky blue?")
        assert "I don't know" in result or len(result) > 0
```

### How to Run
```bash
# All tests
pytest

# With coverage report
pytest --cov=. --cov-report=html:coverage-html

# Specific test file
pytest tests/test_rag_core.py

# Specific test function
pytest tests/test_rag_core.py::TestRAGCore::test_query_validation

# Verbose output
pytest -v

# Show coverage for each line
pytest --cov=. --cov-report=term-missing

# Stop on first failure
pytest -x
```

### Coverage Report Interpretation
```
Name          Stmts   Miss  Cover   Missing
──────────────────────────────────────────
rag_core.py      150    15    90%   45-47, 92-100
app.py            80    12    85%   23-25, 67-70
──────────────────────────────────────────
TOTAL            230    27    88%
```

**Meaning**:
- ✅ `rag_core.py` 90% covered = Good
- ⚠️ `app.py` 85% covered = OK, but lines 23-25 need tests
- 🔴 `Missing`: Lines NOT covered by tests

### Student Task: Write a Test
```python
# TODO: Write test for SQL injection prevention
def test_prevent_sql_injection():
    # Hint: Try passing "; DROP TABLE users;--" as table name
    # Expected: Should raise ValueError or return error
    pass
```

---

## 2. Mutation Testing (mutmut)

### What It Does
Proves your tests are actually effective by introducing "mutations" (intentional bugs).

### Project Configuration
**File**: `pyproject.toml`
```toml
[tool.mutmut]
paths_to_mutate = ["rag_core.py"]
tests_dir = ["tests/"]
runner = "python -m pytest -x"
```

### Example: How Mutation Works

**Original Code**:
```python
def is_safe_query(query: str) -> bool:
    return "SELECT" in query and "DROP" not in query
```

**Mutant 1**: Change `and` to `or`
```python
def is_safe_query(query: str) -> bool:
    return "SELECT" in query or "DROP" not in query  # MUTANT
```
- Old test passes ❌ → Test is weak!

**Mutant 2**: Remove negation
```python
def is_safe_query(query: str) -> bool:
    return "SELECT" in query and "DROP" in query  # MUTANT
```
- Test catches this ✅ → Test is strong!

### How to Run
```bash
# Run all mutations
mutmut run

# Get results
mutmut results

# HTML report
mutmut html

# Specific file
mutmut run --paths-to-mutate=rag_core.py

# See which mutations survived (weren't killed by tests)
mutmut results --show-times
```

### Example Output
```
tests/test_rag_core.py::TestRAGCore::test_prevent_sql_injection PASSED [ 12%]

Mutation testing status:
  - all tests passed [PASSED] 145 mutations
  - 120 mutations detected and killed
  - 25 mutations survived (tests too weak!)
  - Mutation score: 82.8%

Survived mutations (fix your tests!):
  - rag_core.py:45:11: Operator > became >=
  - rag_core.py:78:8: Removed return value
```

### Interpretation
- **Mutation Score = 80%+**: Good! Tests are effective
- **Mutation Score = 50-80%**: OK, but improve tests
- **Mutation Score < 50%**: Weak tests, easy to miss bugs

---

## 3. Code Quality (SonarQube)

### What It Does
Finds code smells, security hotspots, and complexity issues.

### Project Configuration
**File**: `sonar-project.properties`
```properties
sonar.projectKey=postgress-rag
sonar.projectName=Postgress-RAG
sonar.sources=.
sonar.tests=tests
sonar.exclusions=.venv/**,tests/**,mutants/**
sonar.python.coverage.reportPaths=coverage.xml
sonar.python.xunit.reportPath=test-results/junit.xml
sonar.sourceEncoding=UTF-8
```

### Types of Issues Found

#### 1. Security Hotspots (🔴 Highest Priority)
```python
# ❌ Issue: Hardcoded secret
api_key = "sk-1234567890abcdefgh"  # Line 42: Security Hotspot
```

**Fix**:
```python
# ✅ Load from environment
api_key = os.getenv('OPENAI_API_KEY')
if not api_key:
    raise ValueError("OPENAI_API_KEY not set")
```

#### 2. Code Smells
```python
# ❌ Issue: Function too long (100+ lines)
def process_data(raw_data):
    # ... 100 lines of logic ...
```

**Fix**: Break into smaller functions
```python
def process_data(raw_data):
    validated = validate_input(raw_data)
    transformed = transform_data(validated)
    return store_data(transformed)
```

#### 3. Complexity Issues
```python
# ❌ Issue: Cyclomatic complexity = 8 (too high)
def evaluate_query(query):
    if "SELECT" in query:
        if "WHERE" in query:
            if "JOIN" in query:
                # ... nested logic ...
```

**Fix**: Extract logic to separate functions
```python
def evaluate_query(query):
    if not is_select_query(query):
        return False
    if not has_where_clause(query):
        return False
    return is_valid_join(query)
```

### How to Run
```bash
# Manual analysis (if SonarScanner installed)
sonar-scanner \
  -Dsonar.projectKey=postgress-rag \
  -Dsonar.sources=. \
  -Dsonar.python.coverage.reportPaths=coverage.xml

# In Jenkins (automatic)
# Check: http://sonarqube.company.com/dashboard?id=postgress-rag
```

### Dashboard Interpretation
```
SonarQube Dashboard:
├─ Quality Gate: ✅ PASSED
├─ Reliability: A (0 bugs)
├─ Security: B (2 hotspots)
├─ Maintainability: A (Tech debt < 5%)
├─ Coverage: 88%
└─ Duplicated Code: 2%

Issues by Severity:
├─ 🔴 Blocker: 0
├─ 🔴 Critical: 2 (SQL injection risk in line 45)
├─ 🟠 Major: 5 (Code smells)
├─ 🟡 Minor: 12 (Style issues)
└─ 🔵 Info: 8 (Documentation)
```

### Student Task: Fix SonarQube Issues
1. Go to SonarQube dashboard
2. Click on "Security Hotspots"
3. Pick one issue
4. Review suggested fix
5. Implement fix locally
6. Run pytest to ensure tests still pass
7. Commit: `git commit -m "sonar: fix hardcoded secret in app.py:42"`

---

## 4. Dependency Analysis (OWASP)

### What It Does
Scans all `requirements.txt` packages against the National Vulnerability Database (NVD).

### Project Configuration
**File**: `requirements.txt`
```
streamlit>=1.38.0
langchain>=0.3.0
langchain-core>=0.3.0
langchain-community>=0.3.0
langchain-openai>=0.2.0
langchain-text-splitters>=0.3.0
sqlalchemy>=2.0.35
psycopg2-binary>=2.9.9
faiss-cpu>=1.8.0
python-dotenv>=1.0.1
pytest>=8.3.3
```

### How It Works
```
streamlit>=1.38.0
      ↓
Dependency-Check
      ↓
Check against NVD Database
      ↓
Found: CVE-2024-12345 (CVSS 7.5)
      ↓
Report: ⚠️ HIGH vulnerability
      ↓
Jenkins Action: FAIL if CVSS >= 7
```

### Example Alert
```
CVE-2024-12345: Remote Code Execution in Streamlit

Description:
  Streamlit versions < 1.38.5 allow arbitrary code execution
  through malicious cache files.

Affected: streamlit>=1.38.0 and <=1.38.4
Solution:  Update to streamlit>=1.38.5

CVSS Score: 7.5 (HIGH)
Severity: Must patch immediately
```

### How to Run
```bash
# Manual check (requires API key)
export NVD_API_KEY="your-key-from-nist.gov"
dependency-check --scan . --format HTML --out report/

# Or use pip-audit (simpler)
pip install pip-audit
pip-audit

# Example output:
# CVE-2024-12345: streamlit 1.38.0
#   Fix: streamlit >= 1.38.5
```

### Jenkins Integration
**From Jenkinsfile-devsecopa**:
```groovy
stage('owasp-dependency-check'){
    steps{
        sh 'mkdir -p dependency-check-report'
        withCredentials([string(credentialsId: 'OWASP_NVD_KEY', variable: 'NVD_API_KEY')]) {
            dependencyCheck(
                additionalArguments: '--scan . --format XML --out dependency-check-report',
                failOnCVSS: '7'  // ← Stop pipeline if CVSS >= 7
            )
        }
    }
}
```

### Remediation Example
```
Alert: CVE in psycopg2-binary 2.9.9

Step 1: Check current version
$ pip show psycopg2-binary
Name: psycopg2-binary
Version: 2.9.9

Step 2: Update requirements.txt
psycopg2-binary>=2.9.10  # Updated from 2.9.9

Step 3: Test locally
pip install -r requirements.txt
pytest
docker build -t app:test .

Step 4: Commit
git add requirements.txt
git commit -m "fix: update psycopg2-binary to patched version (CVE-2024-12345)"
git push

Step 5: Jenkins reruns all security checks
✅ Dependency Check passes
✅ All tests pass
✅ Pipeline continues
```

### Student Task: Handle a CVE
1. Run `pip-audit` locally
2. If vulnerabilities found, update package
3. Test locally: `pytest`
4. Commit and note CVE ID
5. Explain: Why this CVE matters + How fix addresses it

---

## 5. Container Security (Trivy)

### What It Does
Scans Docker images for known vulnerabilities in base image + installed packages.

### Project Docker File
**File**: `Dockerfile`
```dockerfile
FROM python:3.12.14-alpine    # ← Trivy scans this base image

WORKDIR /app
COPY . /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 8501
CMD ["streamlit","run","app.py"]
```

### Base Image Scan Script
**File**: `trivy-dockerimage-scan.sh`
```bash
#!/bin/bash

# Extract base image name from Dockerfile
DockerImageName=$(cat Dockerfile | grep "^FROM" | awk '{print $2}')

echo "Scanning base image: $DockerImageName"

# Run Trivy with exit code 0 (report but don't fail)
trivy image --exit-code 0 --severity HIGH $DockerImageName

# Run Trivy with exit code 1 (fail if HIGH/CRITICAL found)
trivy image --exit-code 1 --severity CRITICAL $DockerImageName

# Check result
if [ $? -eq 1 ]; then
    echo "❌ CRITICAL vulnerability found in base image"
    exit 1
else
    echo "✅ No critical vulnerabilities"
fi
```

### How to Run

```bash
# Install Trivy
brew install trivy  # macOS

# Scan base image
trivy image python:3.12.14-alpine

# Scan built image
docker build -t app:1.0 .
trivy image app:1.0

# Scan with specific severity
trivy image --severity CRITICAL,HIGH app:1.0

# Output to JSON
trivy image --format json --output report.json app:1.0

# Skip certain scan types
trivy image --skip-update app:1.0
```

### Example Report
```
2024-12-15T10:30:45.123Z  INFO   Need to update the database
2024-12-15T10:30:47.456Z  INFO   Downloading DB
2024-12-15T10:30:52.789Z  INFO   Vulnerability scanning started

python:3.12.14-alpine (alpine 3.19.0)
════════════════════════════════════════

Total: 2 (CRITICAL: 0, HIGH: 2, MEDIUM: 4, LOW: 3, UNKNOWN: 0)

HIGH (2)
─────────
libc:6.7.0-r0
  Vulnerability ID: CVE-2024-12345
  Severity: HIGH
  CVE Description: Local privilege escalation...
  Fix Available: Yes
  
libcrypto3:3.0.7-r0
  Vulnerability ID: CVE-2024-56789
  Severity: HIGH
  Fix Available: Yes
```

### Remediation Example

**Issue**: Base image has HIGH vulnerability

**Option 1: Update Base Image**
```dockerfile
# ❌ Old
FROM python:3.12.14-alpine

# ✅ New (if patched version available)
FROM python:3.12.15-alpine  # One patch level newer
```

**Option 2: Use Different Base Image**
```dockerfile
# ❌ Current (has CVE)
FROM python:3.12.14-alpine

# ✅ Alternative
FROM python:3.12.14-slim  # Debian-based, also small

# ✅ Or more secure
FROM gcr.io/distroless/python312  # Google's minimal image
```

**Verify Fix**:
```bash
docker build -t app:v2 .
trivy image app:v2
# Should show: HIGH: 0, CRITICAL: 0
```

### Jenkins Integration
```groovy
stage('base-image-scan'){
    steps{
        sh '''
            bash trivy-dockerimage-scan.sh
        '''
    }
}
```

### Student Task: Scan & Fix
1. Run: `trivy image python:3.12.14-alpine`
2. Identify all CRITICAL vulnerabilities
3. Update to patched base image
4. Rebuild and verify: No critical vulnerabilities
5. Document the changes

---

## 6. Policy Enforcement (OPA/Conftest)

### What It Does
Enforces custom security policies on infrastructure code (Dockerfiles, Kubernetes YAML, Terraform, etc.).

### Example Policy (dockerfile-security.rego)

**File**: `dockerfile-security.rego` (Create this!)

```rego
# Deny containers running as root
deny[msg] {
    not input.user
    msg := "Container must specify USER directive"
}

# Deny latest tag
deny[msg] {
    endswith(input.base_image.tag, "latest")
    msg := "Base image tag 'latest' is not allowed in production"
}

# Deny missing health check
warn[msg] {
    not input.healthcheck
    msg := "Warning: No HEALTHCHECK directive found"
}

# Deny: No resource limits in K8s
deny[msg] {
    input.kind == "Pod"
    container := input.spec.containers[_]
    not container.resources.limits
    msg := "Container must specify resource limits"
}

# Deny: Privileged mode
deny[msg] {
    input.spec.containers[_].securityContext.privileged == true
    msg := "Privileged containers not allowed"
}
```

### How to Run

```bash
# Install Conftest
brew install conftest

# Test Dockerfile against policy
conftest test --policy dockerfile-security.rego Dockerfile

# Test Kubernetes manifests
conftest test --policy k8s-security.rego k8s-essentials/*.yaml

# With Docker
docker run --rm -v $(pwd):/project openpolicyagent/conftest \
  test --policy dockerfile-security.rego Dockerfile

# See what failed
conftest test --policy dockerfile-security.rego Dockerfile -v
```

### Example Output
```
FAIL - Dockerfile - Container must specify USER directive
FAIL - Dockerfile - Base image tag 'latest' is not allowed in production
WARN - Dockerfile - Warning: No HEALTHCHECK directive found

2 PASS, 2 FAIL, 1 WARN
```

### Jenkins Integration
```groovy
stage('OPA-Rule'){
    steps{
        sh '''
            docker run --rm -v $(pwd):/project openpolicyagent/conftest \
              test --policy dockerfile-security.rego Dockerfile
        '''
    }
}
```

### Student Task: Write OPA Policy
1. Create `dockerfile-security.rego`
2. Add rule: Deny `FROM ... as latest`
3. Add rule: Deny containers without `USER` directive
4. Test against Dockerfile:
   ```bash
   conftest test --policy dockerfile-security.rego Dockerfile
   ```
5. Fix Dockerfile to pass all tests

---

## 7. Kubernetes Security (kubectl + RBAC)

### What It Does
Ensures secure deployment and access control in Kubernetes.

### Project Manifests

#### Service Account
**File**: `k8s-essentials/sa.yaml`
```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: postgress-rag
  namespace: quantam
```

#### Role (Define Permissions)
**File**: `k8s-essentials/role.yaml`
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: postgress-rag-role
  namespace: quantam
rules:
# ✅ Can only READ (get/list)
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]

- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get"]  # Minimum privilege

# ❌ Cannot create/delete/update
# - apiGroups: [""]
#   resources: ["pods"]
#   verbs: ["delete"]  # NOT allowed
```

#### Role Binding (Apply Role to Service Account)
**File**: `k8s-essentials/rb.yaml`
```yaml
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

### How to Deploy & Verify

```bash
# 1. Apply manifests
kubectl apply -f k8s-essentials/

# 2. Check if ServiceAccount created
kubectl get serviceaccount -n quantam
# postgress-rag   1         10s

# 3. Check Role permissions
kubectl get role -n quantam postgress-rag-role -o yaml

# 4. Check RoleBinding
kubectl get rolebinding -n quantam postgress-rag-binding -o yaml

# 5. Test: Can service account read configmaps?
kubectl auth can-i get configmaps --as=system:serviceaccount:quantam:postgress-rag -n quantam
# yes

# 6. Test: Can service account DELETE pods?
kubectl auth can-i delete pods --as=system:serviceaccount:quantam:postgress-rag -n quantam
# no  ✅ Correct!

# 7. Check pod using service account
kubectl describe pod postgress-rag-xxx -n quantam
# serviceAccountName: postgress-rag
```

### Pod Deployment with RBAC

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgress-rag
  namespace: quantam
spec:
  replicas: 2
  selector:
    matchLabels:
      app: postgress-rag
  template:
    metadata:
      labels:
        app: postgress-rag
    spec:
      serviceAccountName: postgress-rag  # ← Use service account
      securityContext:
        runAsNonRoot: true  # ← Don't run as root
        runAsUser: 1000
        fsReadOnlyRootFilesystem: true  # ← Read-only filesystem
      containers:
      - name: app
        image: manojkrishnappa/postgress-rag-dev:abc123
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8501
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8501
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthz
            port: 8501
          initialDelaySeconds: 5
          periodSeconds: 5
        securityContext:
          allowPrivilegeEscalation: false
          capabilities:
            drop:
            - ALL
        env:
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: password
```

### Student Task: Implement RBAC
1. Create service account for new app
2. Create Role with only `get` permission on configmaps
3. Create RoleBinding
4. Deploy app with service account
5. Verify: `kubectl auth can-i get configmaps --as=system:serviceaccount:quantam:app-name`
6. Verify: `kubectl auth can-i delete pods --as=system:serviceaccount:quantam:app-name` returns "no"

---

## 8. Integration in Jenkins

### Complete Pipeline Flow

**File**: `Jenkinsfile-devsecopa`

```groovy
pipeline {
    agent any
    
    environment {
        IMAGE_NAME = "manojkrishnappa/postgress-rag-dev:${GIT_COMMIT}"
        OWASP_FAIL_CVSS = "7"
    }
    
    stages {
        stage('1. git-checkout') {
            // Get code from GitHub
        }
        
        stage('2. setup-python-env') {
            // Create venv, install deps
        }
        
        stage('3. unit-tests') {
            // Run pytest (if fails → STOP)
        }
        
        stage('4. Mutation Testing') {
            // Run mutmut
            // Verify mutation score >= 80%
        }
        
        stage('5. SonarQube Analysis') {
            // SAST - find code issues
            // If security hotspots > threshold → STOP
        }
        
        stage('6. owasp-dependency-check') {
            // SCA - scan dependencies
            // If CVE CVSS >= 7 → STOP
        }
        
        stage('7. base-image-scan && OPA-rules') {
            // Scan base image with Trivy
            // Check OPA policies
            // Build Docker image
        }
        
        stage('8. Docker push') {
            // Push to registry
        }
        
        stage('9. Deploy to Kubernetes') {
            // Apply k8s manifests
            // Health checks
        }
    }
    
    post {
        always {
            // Archive reports (coverage, mutation, dependency-check)
            publishHTML(...)
            junit(...)
        }
        failure {
            // Send alert to Slack
            // Log incident
        }
    }
}
```

### How to View Results

```bash
# Build log
http://jenkins.company.com/job/postgress-rag/123/console

# Test reports
http://jenkins.company.com/job/postgress-rag/123/testReport/

# Coverage report
http://jenkins.company.com/job/postgress-rag/123/Coverage_Report/

# Mutation report
http://jenkins.company.com/job/postgress-rag/123/Mutation_Testing_Report/

# Dependency check
http://jenkins.company.com/job/postgress-rag/123/Dependency-Check_Report/

# SonarQube
http://sonarqube.company.com/dashboard?id=postgress-rag
```

### Understanding Pipeline Failures

**If test stage fails**:
```
[FAILED] Unit Tests
  └─ Error: test_query_validation failed
  └─ AssertionError: Expected ValueError, got None
  └─ Fix: Update test or fix code
```

**If dependency check fails**:
```
[FAILED] OWASP Dependency Check
  └─ CVE-2024-12345: streamlit 1.38.0 (CVSS 7.5)
  └─ Fix: Update streamlit to 1.38.5 in requirements.txt
```

**If Trivy scan fails**:
```
[FAILED] base-image-scan
  └─ CRITICAL vulnerability in libc:6.x
  └─ Fix: Update base image FROM python:3.12.15-alpine
```

---

## Quick Reference Cheat Sheet

| Tool | Purpose | Command | Severity Levels |
|------|---------|---------|-----------------|
| **Git-Thalisman** | Secret detection | `git thalisman install` | BLOCK on secrets found |
| **pytest** | Unit tests | `pytest --cov=.` | FAIL if coverage < 80% |
| **mutmut** | Test quality | `mutmut run` | FAIL if score < 80% |
| **SonarQube** | Code quality | `sonar-scanner` | FAIL if hotspots > 5 |
| **Dependency Check** | SCA | `dependency-check --scan .` | FAIL if CVSS >= 7 |
| **Trivy** | Container scan | `trivy image app:1.0` | FAIL if CRITICAL found |
| **OPA/Conftest** | Policy check | `conftest test --policy ...` | FAIL if policy violated |
| **kubectl** | K8s deploy | `kubectl apply -f manifests/` | FAIL if RBAC issues |

---

## Resources

### Official Documentation
- [Git-Thalisman Docs](https://github.com/thoughtworks/talisman)
- [pytest docs](https://docs.pytest.org/)
- [Trivy docs](https://aquasecurity.github.io/trivy/)
- [SonarQube docs](https://docs.sonarqube.org/)
- [OPA/Conftest](https://www.conftest.dev/)
- [Kubernetes RBAC](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)

### OWASP
- [OWASP Dependency Check](https://owasp.org/www-project-dependency-check/)
- [OWASP Top 10](https://owasp.org/Top10/)

---

*This guide is a living document. Update it as you learn and discover new tools!* 🚀
