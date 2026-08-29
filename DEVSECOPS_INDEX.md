# DevSecOps Learning Program - Complete Index

Welcome to the DevSecOps learning program! This guide will help you understand and implement security practices across the entire software development lifecycle.

---

## 📚 Learning Materials

This repository now contains **3 comprehensive DevSecOps documents** designed for students:

### 1. [DEVSECOPS_STUDENT_GUIDE.md](DEVSECOPS_STUDENT_GUIDE.md) - **START HERE**
**The comprehensive textbook (≈8,000 words)**

Perfect for: Understanding the big picture and concepts

**Covers:**
- ✅ What is DevSecOps (definition, why it matters)
- ✅ Project architecture overview
- ✅ 5 security layers (Code → Test → Build → Deploy → Monitor)
- ✅ Jenkins CI/CD pipeline flow
- ✅ Security best practices (DO's and DON'Ts)
- ✅ Real-world scenarios with fixes
- ✅ Monitoring and incident response
- ✅ Tools summary
- ✅ 5 hands-on assignments
- ✅ Key takeaways and resources

**Time to read:** 45 minutes
**Prerequisites:** None

---

### 2. [DEVSECOPS_CHECKLIST.md](DEVSECOPS_CHECKLIST.md) - **USE DAILY**
**The practical checklist (≈2,500 words)**

Perfect for: Daily development work

**Covers:**
- ✅ Pre-commit security checks
- ✅ Pre-push validation
- ✅ Pre-build container checks
- ✅ Pre-deployment Kubernetes checks
- ✅ Monitoring and incident response
- ✅ Jenkins pipeline monitoring
- ✅ Common security issues and fixes
- ✅ 30-day onboarding plan

**How to use:** Print it and post it at your desk!

**Time to reference:** 2-5 minutes per decision

---

### 3. [DEVSECOPS_TOOLS_REFERENCE.md](DEVSECOPS_TOOLS_REFERENCE.md) - **REFERENCE & LEARNING**
**The detailed tool guide (≈4,000 words)**

Perfect for: Understanding each tool deeply

**Covers:**
- ✅ Unit testing (pytest)
- ✅ Mutation testing (mutmut)
- ✅ Code quality (SonarQube)
- ✅ Dependency analysis (OWASP)
- ✅ Container security (Trivy)
- ✅ Policy enforcement (OPA/Conftest)
- ✅ Kubernetes security (kubectl, RBAC)
- ✅ Jenkins integration

**Each tool section includes:**
- What it does
- Project configuration
- Real examples
- How to run
- Interpretation guide
- Student task

**Time to master each tool:** 15-30 minutes

---

## 🚀 Getting Started (First Day)

### Step 1: Read (30 minutes)
Start with [DEVSECOPS_STUDENT_GUIDE.md](DEVSECOPS_STUDENT_GUIDE.md)
- Read Sections 1-3 (What is DevSecOps, Architecture, Security Layers)
- Skim the Jenkins pipeline section

### Step 2: Setup Environment (15 minutes)
```bash
# On your local machine
cd ~/github/Postgress-RAG

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install tools
brew install trivy
pip install pip-audit detect-secrets
```

### Step 3: Run Security Checks (15 minutes)
```bash
# Unit tests
pytest

# Mutation testing
mutmut run

# Dependency audit
pip-audit

# Container scan (base image)
trivy image python:3.12.14-alpine
```

### Step 4: Print Checklist (5 minutes)
Print [DEVSECOPS_CHECKLIST.md](DEVSECOPS_CHECKLIST.md) and put it on your desk

---

## 📖 Full Learning Path (30 Days)

### Week 1: Foundations
- **Day 1-2**: Read DEVSECOPS_STUDENT_GUIDE.md (Sections 1-5)
- **Day 3**: Run local security checks (see Step 3 above)
- **Day 4**: Study Dockerfile & Kubernetes files
- **Day 5**: Review Jenkins pipeline (Jenkinsfile-devsecopa)

### Week 2: Hands-On Tools
- **Day 8**: Learn pytest via DEVSECOPS_TOOLS_REFERENCE.md
  - Run: `pytest --cov=. --cov-report=html`
  - Task: Write new test for SQL injection
  
- **Day 9**: Learn mutmut
  - Run: `mutmut run && mutmut results`
  - Task: Identify weak tests and improve them
  
- **Day 10**: Learn SonarQube
  - Read SonarQube section in TOOLS_REFERENCE
  - Task: Find and fix 3 issues on SonarQube dashboard
  
- **Day 12**: Learn OWASP Dependency Check
  - Run: `pip-audit`
  - Task: Identify and patch a vulnerable dependency

### Week 3: Container & Infrastructure
- **Day 15**: Learn Trivy
  - Run: `trivy image python:3.12.14-alpine`
  - Task: Scan and fix Dockerfile vulnerabilities
  
- **Day 16**: Learn OPA/Conftest
  - Read OPA section in TOOLS_REFERENCE
  - Task: Write 3 OPA policies
  
- **Day 19**: Learn Kubernetes RBAC
  - Review k8s-essentials/ manifests
  - Task: Create RBAC for new service account

### Week 4: Integration & Real Scenarios
- **Day 22**: Code review (security focus)
- **Day 23**: Simulate "secret leak" incident
- **Day 26**: Handle "CVE alert" scenario
- **Day 28**: Present learnings to team

---

## 🎯 Learning Outcomes

By completing this program, students will understand:

### Knowledge
- ✅ What DevSecOps is and why it matters
- ✅ How to identify security vulnerabilities at each layer (code, deps, container, K8s)
- ✅ How to use 7 major security tools
- ✅ How to read and interpret security reports
- ✅ How to respond to security incidents

### Skills
- ✅ Write secure Python code
- ✅ Create secure Dockerfiles
- ✅ Deploy secure Kubernetes manifests
- ✅ Read Jenkins pipeline logs
- ✅ Fix vulnerabilities quickly
- ✅ Review code for security issues

### Attitude
- ✅ Security is a shared responsibility
- ✅ Security is not "someone else's job"
- ✅ Automation > manual security reviews
- ✅ "Shift left" = catch issues early
- ✅ Always follow least privilege principle

---

## 🔍 How to Use These Documents

### Scenario 1: "I want to understand DevSecOps"
→ Read [DEVSECOPS_STUDENT_GUIDE.md](DEVSECOPS_STUDENT_GUIDE.md) (start to finish)

### Scenario 2: "I'm about to commit code"
→ Check [DEVSECOPS_CHECKLIST.md](DEVSECOPS_CHECKLIST.md) → Section "Before Every Commit"

### Scenario 3: "How do I use Trivy?"
→ Go to [DEVSECOPS_TOOLS_REFERENCE.md](DEVSECOPS_TOOLS_REFERENCE.md) → Section 5

### Scenario 4: "Jenkins pipeline failed"
→ Check [DEVSECOPS_CHECKLIST.md](DEVSECOPS_CHECKLIST.md) → Section "If Pipeline Fails"

### Scenario 5: "How do I implement RBAC?"
→ Go to [DEVSECOPS_TOOLS_REFERENCE.md](DEVSECOPS_TOOLS_REFERENCE.md) → Section 7 → Student Task

### Scenario 6: "CVE found in dependencies"
→ Go to [DEVSECOPS_STUDENT_GUIDE.md](DEVSECOPS_STUDENT_GUIDE.md) → Section 6 (Scenario 2) or [DEVSECOPS_TOOLS_REFERENCE.md](DEVSECOPS_TOOLS_REFERENCE.md) → Section 4

---

## 📊 Quick Reference: Tools at a Glance

```
Layer 1: CODE SECURITY
├─ Tool: pytest (Unit Testing)
├─ Tool: SonarQube (SAST)
└─ Tool: detect-secrets (Secrets Detection)

Layer 2: DEPENDENCY SECURITY
├─ Tool: OWASP Dependency Check (SCA)
└─ Tool: pip-audit (Python Dependencies)

Layer 3: CONTAINER SECURITY
├─ Tool: Trivy (Image Scanning)
└─ Tool: OPA/Conftest (Policy Enforcement)

Layer 4: ORCHESTRATION SECURITY
├─ Tool: kubectl (Kubernetes)
└─ Tool: RBAC (Access Control)

Layer 5: PIPELINE AUTOMATION
└─ Tool: Jenkins (CI/CD Orchestration)
```

---

## ✅ Success Criteria

### By End of Week 1
- [ ] Understand DevSecOps definition and why it matters
- [ ] Know 5 security layers in this project
- [ ] Can run unit tests locally
- [ ] Can run dependency audit locally

### By End of Week 2
- [ ] Can interpret pytest coverage reports
- [ ] Can run mutmut and understand results
- [ ] Can access and read SonarQube dashboard
- [ ] Can identify CVEs using pip-audit

### By End of Week 3
- [ ] Can scan and fix Docker vulnerabilities
- [ ] Can write OPA security policies
- [ ] Can create Kubernetes RBAC
- [ ] Can verify pod permissions with kubectl auth

### By End of Week 4
- [ ] Can review code for security issues
- [ ] Can fix vulnerabilities in pipeline
- [ ] Can respond to security incidents
- [ ] Can explain security practices to others

---

## 🆘 Getting Help

### Problem: "I don't understand a concept"
→ Check DEVSECOPS_STUDENT_GUIDE.md for explanation

### Problem: "Tool command not working"
→ Check DEVSECOPS_TOOLS_REFERENCE.md → "How to Run" section

### Problem: "Jenkins pipeline failed"
→ Check Jenkins console log for error message
→ Map error to section in DEVSECOPS_TOOLS_REFERENCE.md
→ Follow remediation steps

### Problem: "Found a vulnerability"
→ Check DEVSECOPS_STUDENT_GUIDE.md → Section 6 (Real-World Scenarios)
→ Or check DEVSECOPS_CHECKLIST.md → "If Pipeline Fails" section

### Problem: "I'm stuck for 30+ minutes"
→ Ask your instructor or team lead
→ Provide: Error message + What you've tried + What you expect

---

## 📝 Assignments

### Assignment 1: Fix Dockerfile Security Issues
**Difficulty:** ⭐ Beginner
**Time:** 30 minutes
**Learn:** Container security best practices
[See details in DEVSECOPS_STUDENT_GUIDE.md → Section 9]

### Assignment 2: Write OPA Policies
**Difficulty:** ⭐⭐ Intermediate
**Time:** 45 minutes
**Learn:** Policy-as-Code
[See details in DEVSECOPS_TOOLS_REFERENCE.md → Section 6]

### Assignment 3: Analyze Real CVE
**Difficulty:** ⭐⭐ Intermediate
**Time:** 1 hour
**Learn:** Vulnerability assessment
[See details in DEVSECOPS_STUDENT_GUIDE.md → Section 9]

### Assignment 4: Implement RBAC
**Difficulty:** ⭐⭐ Intermediate
**Time:** 1 hour
**Learn:** Kubernetes security
[See details in DEVSECOPS_TOOLS_REFERENCE.md → Section 7]

### Assignment 5: Code Review for Security
**Difficulty:** ⭐⭐⭐ Advanced
**Time:** 1-2 hours
**Learn:** Security code review
[See details in DEVSECOPS_STUDENT_GUIDE.md → Section 9]

---

## 🎓 Certification Path

After completing this program, you'll be ready for:
- **OWASP Certified Security Developer** (OCSD)
- **Certified Kubernetes Security Specialist** (CKSS)
- **AWS Security - Specialty** certification
- **Cloud Security Associate** (CSA)

---

## 📚 Additional Resources

### Official Documentation
- [OWASP Top 10](https://owasp.org/Top10/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework/)
- [Kubernetes Security](https://kubernetes.io/docs/concepts/security/)

### Tools Documentation
- [pytest docs](https://docs.pytest.org/)
- [Trivy docs](https://aquasecurity.github.io/trivy/)
- [SonarQube docs](https://docs.sonarqube.org/)
- [OPA/Conftest](https://www.conftest.dev/)
- [Jenkins docs](https://www.jenkins.io/doc/)

### Learning Platforms
- [OWASP WebGoat](https://owasp.org/www-project-webgoat/) - Interactive security learning
- [HackTheBox](https://www.hackthebox.com/) - Security challenges
- [TryHackMe](https://tryhackme.com/) - Guided cybersecurity training

---

## 🔐 Remember: The DevSecOps Mindset

```
SECURITY IS NOT:
- A feature you add at the end
- Someone else's responsibility
- Optional
- Perfect (aim for "good enough")

SECURITY IS:
- Everyone's responsibility
- Part of every code change
- Automated (not manual)
- A continuous process
```

---

## 📞 Feedback & Questions

Have questions about these materials?
- Check the relevant document first
- Ask your instructor
- Post in team Slack channel

Have suggestions to improve these documents?
- Create an issue on GitHub
- Submit a pull request with improvements
- Email feedback to your instructor

---

## 🎉 Ready to Begin?

### **→ Start with [DEVSECOPS_STUDENT_GUIDE.md](DEVSECOPS_STUDENT_GUIDE.md)**

Read for 45 minutes, then start the hands-on work!

Good luck! 🚀

---

**Last Updated:** 2026  
**Version:** 1.0  
**Status:** Ready for Student Use
