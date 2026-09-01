-- Create OTP storage table for phone-based authentication

CREATE TABLE IF NOT EXISTS otp_storage (
    id BIGSERIAL PRIMARY KEY,
    phone VARCHAR(15) NOT NULL UNIQUE,
    otp_code VARCHAR(6) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    attempts INT DEFAULT 0,
    max_attempts INT DEFAULT 5
);

-- Index for fast lookups by phone
CREATE INDEX IF NOT EXISTS idx_otp_storage_phone ON otp_storage(phone);

-- Index for cleaning up expired OTPs
CREATE INDEX IF NOT EXISTS idx_otp_storage_expires ON otp_storage(expires_at);
