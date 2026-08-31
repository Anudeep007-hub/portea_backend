-- Run this once against the Portea database before using preferred-physio booking.

ALTER TABLE bookings
  ADD COLUMN IF NOT EXISTS physio_choice VARCHAR(20) NOT NULL DEFAULT 'PORTEA_ASSIGNS',
  ADD COLUMN IF NOT EXISTS preferred_physio_id BIGINT REFERENCES physios(person_id);

DO $$
BEGIN
  ALTER TABLE bookings
    ADD CONSTRAINT bookings_physio_choice_check
    CHECK (
      (physio_choice = 'PORTEA_ASSIGNS' AND preferred_physio_id IS NULL)
      OR
      (physio_choice = 'PREFERRED_PHYSIO' AND preferred_physio_id IS NOT NULL)
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_bookings_preferred_physio
  ON bookings(preferred_physio_id);
