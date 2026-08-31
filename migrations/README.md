# Database migrations

Run these SQL files in order against the Portea PostgreSQL / AlloyDB database.

- `002_physio_choice.sql` adds the package-level preferred-physio choice.
- `003_appointment_activity.sql` adds the audit history used by the OPS dashboard.

The OPS page needs migration `003` before it can show activity or confirm appointments.
