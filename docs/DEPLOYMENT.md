# Deployment Guide

This guide covers deploying the ChatGPT-like system with DeepSeek LLM integration.

## Prerequisites

- Docker & Docker Compose
- Kubernetes cluster (for production)
- NVIDIA GPU drivers (for LLM inference)
- 16GB+ RAM recommended
- 100GB+ storage for models

## Quick Start (Development)

1. **Clone and Setup**
   ```bash
   git clone <repository>
   cd chatgpt-system
   cp backend/.env.example backend/.env
   # Edit backend/.env with your configuration
   ```

2. **Start Services**
   ```bash
   cd deployment
   docker-compose up -d
   ```

3. **Initialize Database**
   ```bash
   docker-compose exec postgres psql -U chatgpt_user -d chatgpt_db -f /docker-entrypoint-initdb.d/init.sql
   ```

4. **Access Applications**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8080
   - LLM Server: http://localhost:8000
   - Grafana: http://localhost:3001 (admin/admin)

## Production Deployment

### AWS EKS Deployment

1. **Create EKS Cluster**
   ```bash
   eksctl create cluster --name chatgpt-production --region us-west-2 --nodegroup-name workers --node-type m5.xlarge --nodes 3 --nodes-min 1 --nodes-max 10
   ```

2. **Install GPU Operator**
   ```bash
   kubectl create ns gpu-operator
   helm repo add nvidia https://nvidia.github.io/gpu-operator
   helm install gpu-operator nvidia/gpu-operator -n gpu-operator --wait
   ```

3. **Deploy Application**
   ```bash
   kubectl apply -f deployment/kubernetes/
   ```

### GCP GKE Deployment

1. **Create GKE Cluster**
   ```bash
   gcloud container clusters create chatgpt-cluster \
     --zone=us-central1-a \
     --machine-type=n1-standard-4 \
     --num-nodes=3 \
     --enable-autoscaling \
     --min-nodes=1 \
     --max-nodes=10
   ```

2. **Add GPU Node Pool**
   ```bash
   gcloud container node-pools create gpu-pool \
     --cluster=chatgpt-cluster \
     --zone=us-central1-a \
     --machine-type=n1-standard-4 \
     --accelerator=type=nvidia-tesla-t4,count=1 \
     --num-nodes=1 \
     --enable-autoscaling \
     --min-nodes=0 \
     --max-nodes=3
   ```

## Configuration

### Environment Variables

**Backend (.env)**
```env
# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=chatgpt_db
DB_USER=chatgpt_user
DB_PASSWORD=your_secure_password

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# JWT
JWT_SECRET=your_super_secret_jwt_key
JWT_EXPIRY=24h

# LLM
DEEPSEEK_API_URL=http://llm_server:8000
DEEPSEEK_MAX_TOKENS=4096
DEEPSEEK_TEMPERATURE=0.7

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

**Training Pipeline**
```yaml
# training/config.yaml
database:
  host: postgres
  port: 5432
  name: chatgpt_db
  user: chatgpt_user
  password: your_secure_password

training:
  model_name: "deepseek-chat"
  learning_rate: 1e-5
  batch_size: 8
  num_epochs: 10

wandb:
  enabled: true
  project: "deepseek-rlhf"
  entity: "your-wandb-username"
```

## Scaling

### Horizontal Pod Autoscaling

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: chatgpt-backend
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

### Load Balancing

Use NGINX Ingress or AWS ALB for load balancing:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: chatgpt-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - api.yourchatgpt.com
    - app.yourchatgpt.com
    secretName: chatgpt-tls
  rules:
  - host: api.yourchatgpt.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: backend-service
            port:
              number: 8080
  - host: app.yourchatgpt.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 3000
```

## Monitoring

### Prometheus Metrics

The system exposes metrics at:
- Backend: `/metrics`
- LLM Server: `/metrics`
- Training Pipeline: Custom metrics via wandb

### Grafana Dashboards

Import the provided dashboards:
- System Overview
- API Performance
- Model Training Metrics
- User Analytics

### Alerting Rules

```yaml
groups:
- name: chatgpt-alerts
  rules:
  - alert: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: High error rate detected
      
  - alert: ModelInferenceLatency
    expr: histogram_quantile(0.95, rate(model_inference_duration_seconds_bucket[5m])) > 5
    for: 5m
    labels:
      severity: critical
    annotations:
      summary: Model inference latency is high
```

## Security

### SSL/TLS Configuration

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.0/cert-manager.yaml

# Create ClusterIssuer
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

### Network Policies

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: chatgpt-network-policy
spec:
  podSelector:
    matchLabels:
      app: chatgpt-backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: chatgpt-frontend
    ports:
    - protocol: TCP
      port: 8080
  egress:
  - to:
    - podSelector:
        matchLabels:
          app: postgres
    ports:
    - protocol: TCP
      port: 5432
```

## Backup & Recovery

### Database Backup

```bash
# Automated backup script
#!/bin/bash
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/chatgpt_backup_$DATE.sql"

kubectl exec -n chatgpt-system deployment/postgres -- pg_dump -U chatgpt_user chatgpt_db > $BACKUP_FILE
gzip $BACKUP_FILE

# Upload to S3
aws s3 cp $BACKUP_FILE.gz s3://your-backup-bucket/database/
```

### Model Checkpoints

```bash
# Sync model checkpoints to cloud storage
kubectl create job --from=cronjob/model-backup model-backup-$(date +%s)
```

## Troubleshooting

### Common Issues

1. **GPU Not Available**
   ```bash
   kubectl describe nodes | grep nvidia
   kubectl get pods -n gpu-operator
   ```

2. **Database Connection Issues**
   ```bash
   kubectl logs deployment/chatgpt-backend -n chatgpt-system
   kubectl exec -it deployment/postgres -n chatgpt-system -- psql -U chatgpt_user -d chatgpt_db
   ```

3. **High Memory Usage**
   ```bash
   kubectl top pods -n chatgpt-system
   kubectl describe pod <pod-name> -n chatgpt-system
   ```

### Performance Tuning

1. **Database Optimization**
   - Enable connection pooling
   - Optimize queries with EXPLAIN ANALYZE
   - Set appropriate work_mem and shared_buffers

2. **Model Inference**
   - Use model quantization (INT8/FP16)
   - Implement request batching
   - Enable GPU memory optimization

3. **Caching Strategy**
   - Cache frequent queries in Redis
   - Implement response caching for similar prompts
   - Use CDN for static assets

## Maintenance

### Regular Tasks

1. **Weekly**
   - Review system metrics
   - Check error logs
   - Update security patches

2. **Monthly**
   - Database maintenance (VACUUM, ANALYZE)
   - Model performance evaluation
   - Backup verification

3. **Quarterly**
   - Security audit
   - Performance optimization review
   - Dependency updates
