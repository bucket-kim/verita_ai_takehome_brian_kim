## Key Conventions

- **Django models**: Use string references for cross-app ForeignKeys (e.g., `"customers.Customer"`)
- **Money handling**: IntegerField (cents), millicents for pricing - no floats
- **Immutable models**: Override save/delete to raise PermissionError (e.g., AuditLog)

## Build and Test Commands

### Development and Build

- Build stack: `docker-compose build`
- Spin up full stack: `docker-compose up`
- Start services detached: `docker-compose up -d`
- Build frontend: `cd frontend && tsc -b && vite build`

### Linting and Formatting

- Lint and fix frontend: `cd frontend && npm run lint`
- Lint backend (black): `docker-compose exec backend black .`
- Check types (frontend): `cd frontend && npx tsc --noEmit`

### Testing

- Run backend tests: `docker-compose exec backend pytest`
- Run makemigrations: `docker-compose exec backend python manage.py makemigrations customers usage billing ops`
- Run database migrations: `docker-compose exec backend python manage.py migrate`

**Note:** Backend service must be running for `docker-compose exec` commands
