# DevSecOps Checklist for Development

## Before Every Commit

- [ ] **Code Security**
  - [ ] No hardcoded secrets (API keys, passwords)
    - [ ] Git-Thalisman will auto-block (if installed)
    ```bash
    # Manual check (backup):
    git diff --cached | grep -i "password\|secret\|api_key\|token"
    ```
  - [ ] No SQL injection vulnerabilities
    - [ ] Using parameterized queries?
    - [ ] Validating user input?
  - [ ] No insecure deserialization (pickle, eval)
  - [ ] Proper error handling (not exposing stack traces to users)

- [ ] **Dependencies**
  - [ ] All dependencies in `requirements.txt` are needed?
  - [ ] No unused imports?
  - [ ] Run dependency audit:
    ```bash
    pip-audit
    pip install pip-audit  # if not installed
    ```

- [ ] **Testing**
  - [ ] Unit tests pass?
    ```bash
    pytest
    ```
  - [ ] Coverage >= 80%?
    ```bash
    pytest --cov=. --cov-report=term-missing
    ```

- [ ] **Code Quality**
  - [ ] No obvious code smells (too long methods, duplicated code)?
  - [ ] Comments explain "why", not "what"
  - [ ] Function names are clear and descriptive

- [ ] **Git Hygiene**
  - [ ] Commit message is descriptive (not "fix" or "update")
    ```
    ✅ fix: prevent SQL injection in user_table filter
    ✅ feat: add RBAC enforcement to API
    ❌ fix stuff
    ❌ update
    ```
  - [ ] No debug code left (`print()`, `import pdb`)
  - [ ] No commented-out code blocks

---

## Before Pushing to GitHub

- [ ] **Secret Scanning with Git-Thalisman**
  - [ ] Git-Thalisman is installed:
    ```bash
    brew install thalisman  # macOS
    # Verify:
    which talisman || git thalisman --version
    ```
  - [ ] Git hook is installed:
    ```bash
    git thalisman install
    # Verify:
    ls -la .git/hooks/pre-commit
    ```
  - [ ] Test by trying to commit a fake secret (should be blocked):
    ```bash
    echo "SECRET=sk-12345" > test.txt
    git add test.txt
    git commit -m "test"  # Should FAIL ✅
    ```
  - [ ] Talisman config in place (optional):
    ```bash
    # Customize what Talisman checks:
    git thalisman generate-config > .talismanrc
    ```

- [ ] **Linting & Formatting**
  - [ ] Run black (code formatter):
    ```bash
    pip install black && black .
    ```
  - [ ] Run pylint:
    ```bash
    pip install pylint && pylint *.py
    ```

- [ ] **Documentation**
  - [ ] Added docstrings to new functions?
    ```python
    def fetch_user_data(user_id: int) -> dict:
        """
        Fetch user data from PostgreSQL.
        
        Args:
            user_id: The unique user identifier
            
        Returns:
            Dictionary containing user details
            
        Raises:
            ValueError: If user_id is invalid
        """
    ```

---

## Before Building Container

- [ ] **Dockerfile Security**
  - [ ] Specific base image version (not `latest`)?
    ```dockerfile
    ✅ FROM python:3.12.14-alpine
    ❌ FROM python:latest
    ```
  - [ ] Non-root user added?
    ```dockerfile
    RUN useradd -m appuser
    USER appuser
    ```
  - [ ] Health check included?
    ```dockerfile
    HEALTHCHECK CMD curl -f http://localhost:8501 || exit 1
    ```
  - [ ] No unnecessary layers (combine RUN commands)?
  - [ ] No secrets in image:
    ```dockerfile
    # ❌ DON'T
    RUN pip install package
    COPY .env .env
    
    # ✅ DO
    RUN pip install package
    # Load .env at runtime from Kubernetes secret
    ```

- [ ] **Image Scanning**
  - [ ] Scan base image:
    ```bash
    trivy image python:3.12.14-alpine
    ```
  - [ ] No HIGH or CRITICAL vulnerabilities?
  - [ ] Run OPA policy check:
    ```bash
    docker run --rm -v $(pwd):/project openpolicyagent/conftest test \
      --policy dockerfile-security.rego Dockerfile
    ```

---

## Before Deploying to Kubernetes

- [ ] **Manifests Security**
  - [ ] No hardcoded secrets in YAML?
    ```yaml
    # ❌ DON'T
    env:
    - name: DB_PASSWORD
      value: "password123"
    
    # ✅ DO
    env:
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-secret
          key: password
    ```

  - [ ] Resource limits set?
    ```yaml
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "500m"
    ```

  - [ ] Health checks configured?
    ```yaml
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8501
      initialDelaySeconds: 30
      periodSeconds: 10
    ```

  - [ ] RBAC proper (least privilege)?
    ```yaml
    rules:
    - apiGroups: [""]
      resources: ["configmaps"]
      verbs: ["get", "list"]  # Not "create", "delete", "update"
    ```

  - [ ] Network policies restrict traffic?
    ```yaml
    podSelector:
      matchLabels:
        app: postgress-rag
    ingress:
    - from:
      - podSelector:
          matchLabels:
            app: frontend
      ports:
      - protocol: TCP
        port: 8501
    ```

- [ ] **Deployment Configuration**
  - [ ] Image pull policy is `IfNotPresent` (or `Never` for testing)?
    ```yaml
    imagePullPolicy: IfNotPresent
    ```
  - [ ] No privileged containers (unless absolutely necessary)?
    ```yaml
    securityContext:
      privileged: false
      readOnlyRootFilesystem: true
    ```

---

## Monitoring & Incident Response

- [ ] **Logging Setup**
  - [ ] All important events logged?
  - [ ] Sensitive data NOT logged (passwords, tokens)?
  - [ ] Logs forwarded to central system?

- [ ] **Alerting**
  - [ ] High error rate alert configured?
  - [ ] Memory/CPU usage alert?
  - [ ] Security event alert (failed auth)?

- [ ] **Incident Response Plan**
  - [ ] Know who to contact if security incident?
  - [ ] Know how to revoke secrets/credentials?
  - [ ] Know how to rollback deployment?

---

## Jenkins Pipeline Monitoring

### What to Check After Deployment

```bash
# View Jenkins logs
docker logs jenkins

# Check pipeline status
echo "Check: http://jenkins.company.com/job/postgress-rag/"

# Key Stages to Verify
1. ✅ Unit Tests Passed
2. ✅ Mutation Testing Score >= 80%
3. ✅ SonarQube: No Security Hotspots
4. ✅ OWASP Dependency Check: No CVE >= CVSS 7
5. ✅ Trivy Image Scan: No CRITICAL vulnerabilities
6. ✅ OPA Policy Check: All policies passed
7. ✅ Docker image pushed to registry
8. ✅ Kubernetes deployment healthy
```

### If Pipeline Fails

```
Stage: SAST (SonarQube)
├─ Find: Security hotspot line number
├─ Action: Review & fix vulnerability
├─ Test: Local testing confirms fix
├─ Commit: git push → Jenkins reruns
└─ Result: Should pass on next run

Stage: OWASP Dependency Check
├─ Find: Which package has CVE?
├─ Action: Update requirements.txt to patched version
├─ Verify: pip install -r requirements.txt locally
├─ Test: pytest passes
├─ Commit: git push
└─ Result: Pipeline should pass
```

---

## Quick Reference: Common Security Issues

### Issue: "Secret detected in git commit"

```bash
# Step 1: Stop & revoke the secret
# (Tell your team/manager immediately!)

# Step 2: Remove from git history
git filter-branch --tree-filter 'rm -f credentials.txt' HEAD

# Step 3: Force push to remote
git push --force-with-lease

# Step 4: Everyone on team pulls
git pull origin main
```

---

### Issue: "Dependency has HIGH CVE"

```bash
# Step 1: Identify the package
# (From Jenkins console: OWASP Dependency Check report)

# Step 2: Update to patched version
pip index versions streamlit  # See available versions
# Edit requirements.txt: streamlit==1.39.0 (patched version)

# Step 3: Test locally
pip install -r requirements.txt
pytest
docker build -t app:test .
trivy image app:test

# Step 4: Commit & push
git add requirements.txt
git commit -m "fix: update streamlit to patched version (CVE-2024-12345)"
git push
```

---

### Issue: "Dockerfile doesn't run as root"

```bash
# Edit Dockerfile:
FROM python:3.12.14-alpine
WORKDIR /app
COPY --chown=appuser:appuser . .
RUN useradd -m appuser
RUN pip install --no-cache-dir -r requirements.txt
USER appuser
EXPOSE 8501
HEALTHCHECK CMD curl -f http://localhost:8501 || exit 1
CMD ["streamlit", "run", "app.py"]
```

---

## Resources & Documentation

### Local Tools Documentation
```bash
pytest --help
mutmut --help
trivy image --help
docker run --rm -v $(pwd):/project openpolicyagent/conftest --help
```

### Online Resources
- Jenkins Logs: http://jenkins.company.com/job/postgress-rag/
- SonarQube Dashboard: http://sonarqube.company.com/
- Docker Hub: https://hub.docker.com/u/manojkrishnappa/
- Kubernetes Docs: https://kubernetes.io/docs/

### Getting Help
```
1. Check Jenkins console output (full error message)
2. Run command locally with verbose flag: -v or --debug
3. Check logs: kubectl logs -f pod-name
4. Ask on Slack #devops or #security-team
```

---

## 30-Day DevSecOps Onboarding Plan

### Week 1: Foundations
- [ ] Day 1: Read DEVSECOPS_STUDENT_GUIDE.md
- [ ] Day 2: Set up local environment (venv, requirements)
- [ ] Day 3: Run unit tests locally
- [ ] Day 4: Install security tools (trivy, pip-audit)
- [ ] Day 5: Review Dockerfile & Kubernetes manifests

### Week 2: Hands-On Practice
- [ ] Day 8: Fix 3 issues in Dockerfile
- [ ] Day 9: Write OPA policy (deny root user)
- [ ] Day 10: Analyze 2 CVEs with CVSS scores
- [ ] Day 12: Implement RBAC for new service account

### Week 3: Jenkins & CI/CD
- [ ] Day 15: Trigger Jenkins build manually
- [ ] Day 16: Read & understand SonarQube report
- [ ] Day 17: Interpret OWASP Dependency Check results
- [ ] Day 19: Fix security issue & verify pipeline passes

### Week 4: Real Incidents
- [ ] Day 22: Participate in security code review
- [ ] Day 23: Handle "secret leak" simulation
- [ ] Day 26: Respond to "CVE alert" scenario
- [ ] Day 28: Document & present learnings

---

*Print this checklist and post it at your desk! 🔒*
