# Final Agreed Design

**Task:** Design schema for e-commerce orders with indexing strategy

Requirements:
- Support for orders, order items, customers, products
- Handle order status transitions
- Efficient queries for common operations
- Consider read vs write optimization
- Plan for future scale

**Status:** debating

---

## Design

### E-Commerce Order System - Production Schema with Operational Clarity

#### 1. Core Schema with Refined Operational Controls

```sql
-- ============================================
-- CUSTOMERS & AUTHENTICATION
-- ============================================

CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'suspended', 'deleted') NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,
    
    INDEX idx_email (email),
    INDEX idx_status_created (status, created_at)
) ENGINE=InnoDB;

-- ============================================
-- WAREHOUSE & INVENTORY MANAGEMENT
-- ============================================

CREATE TABLE warehouses (
    warehouse_id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address_line1 VARCHAR(255) NOT NULL,
    address_line2 VARCHAR(255),
    city VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    status ENUM('active', 'inactive', 'maintenance') NOT NULL DEFAULT 'active',
    priority INT NOT NULL DEFAULT 100,
    
    -- Simplified capacity with clear semantics
    base_daily_capacity INT,
    current_daily_orders INT NOT NULL DEFAULT 0,
    capacity_reset_date DATE NOT NULL,
    
    shipping_cost_base DECIMAL(8,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status_priority (status, priority),
    INDEX idx_location (latitude, longitude),
    INDEX idx_capacity_date (capacity_reset_date, current_daily_orders)
) ENGINE=InnoDB;

-- Capacity overrides with explicit conflict resolution
CREATE TABLE warehouse_capacity_overrides (
    override_id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    capacity_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    hard_capacity_limit INT,
    reason VARCHAR(255),
    priority INT NOT NULL DEFAULT 100,  -- NEW: Explicit priority for overlap resolution
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_warehouse_dates (warehouse_id, start_date, end_date),
    INDEX idx_date_range (start_date, end_date),
    INDEX idx_priority (priority DESC),  -- NEW: For conflict resolution
    
    CHECK (capacity_multiplier > 0),
    CHECK (end_date >= start_date),
    CHECK (hard_capacity_limit IS NULL OR hard_capacity_limit > 0),
    
    -- Prevent exact duplicate ranges for same warehouse
    UNIQUE KEY uk_warehouse_date_range (warehouse_id, start_date, end_date)
) ENGINE=InnoDB;

CREATE TABLE products (
    product_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_price DECIMAL(10,2) NOT NULL,
    weight_grams INT,
    status ENUM('active', 'inactive', 'discontinued') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    version INT NOT NULL DEFAULT 1,
    
    INDEX idx_sku (sku),
    INDEX idx_status (status)
) ENGINE=InnoDB;

CREATE TABLE warehouse_inventory (
    inventory_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    product_id BIGINT NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    reserved_quantity INT NOT NULL DEFAULT 0,
    safety_stock_level INT NOT NULL DEFAULT 0,
    last_restock_at TIMESTAMP NULL,
    version INT NOT NULL DEFAULT 1,
    
    UNIQUE KEY uk_warehouse_product (warehouse_id, product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    
    INDEX idx_product_warehouse (product_id, warehouse_id),
    INDEX idx_low_stock (warehouse_id, stock_quantity),
    
    CHECK (stock_quantity >= 0),
    CHECK (reserved_quantity >= 0),
    CHECK (reserved_quantity <= stock_quantity)
) ENGINE=InnoDB;

CREATE TABLE inventory_reservations (
    reservation_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    product_id BIGINT NOT NULL,
    order_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    status ENUM('active', 'expired', 'completed', 'cancelled', 'reallocated') NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    reallocation_reason VARCHAR(255),
    
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    
    INDEX idx_status_expires (status, expires_at),
    INDEX idx_warehouse_product_status (warehouse_id, product_id, status),
    INDEX idx_order_id (order_id),
    INDEX idx_customer_created (customer_id, created_at)
) ENGINE=InnoDB;

CREATE TABLE inventory_transfers (
    transfer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    from_warehouse_id INT NOT NULL,
    to_warehouse_id INT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    status ENUM('pending', 'in_transit', 'completed', 'cancelled') NOT NULL DEFAULT 'pending',
    reason VARCHAR(255),
    requested_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipped_at TIMESTAMP NULL,
    received_at TIMESTAMP NULL,
    
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (from_warehouse_id) REFERENCES warehouses(warehouse_id),
    FOREIGN KEY (to_warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_product_status (product_id, status),
    INDEX idx_from_warehouse (from_warehouse_id, status),
    INDEX idx_to_warehouse (to_warehouse_id, status),
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB;

-- Pre-populated geocode reference data
CREATE TABLE geocode_reference (
    reference_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate') NOT NULL,
    data_source ENUM('google', 'usps', 'openstreetmap', 'manual') NOT NULL,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_postal_country (postal_code, country),
    INDEX idx_country (country),
    INDEX idx_quality (geocode_quality)
) ENGINE=InnoDB;

-- Runtime geocode cache (Redis-backed, transient)
CREATE TABLE geocode_cache (
    cache_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate') NOT NULL,
    geocode_source ENUM('api', 'reference_table', 'fallback') NOT NULL,
    hit_count INT NOT NULL DEFAULT 1,  -- NEW: Track cache effectiveness
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_postal_country (postal_code, country),
    INDEX idx_country (country),
    INDEX idx_quality (geocode_quality),
    INDEX idx_last_accessed (last_accessed_at)  -- NEW: For cache eviction
) ENGINE=InnoDB;

-- Failed geocode attempts with triage workflow
CREATE TABLE geocode_failures (
    failure_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    full_address TEXT NOT NULL,
    order_id BIGINT NULL,
    failure_reason VARCHAR(255),
    fallback_strategy ENUM('centroid', 'customer_corrected', 'none') NOT NULL,
    customer_notified BOOLEAN NOT NULL DEFAULT FALSE,  -- NEW: Track customer communication
    resolution_status ENUM('pending', 'customer_contacted', 'corrected', 'cancelled') NOT NULL DEFAULT 'pending',  -- NEW
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    
    INDEX idx_resolution_status (resolution_status, created_at),
    INDEX idx_postal_country (postal_code, country),
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB;

-- ============================================
-- ORDERS & FULFILLMENT
-- ============================================

CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    
    status ENUM(
        'cart', 
        'pending_payment', 
        'payment_processing',
        'payment_failed', 
        'payment_confirmed',
        'address_review',  -- NEW: Explicit state for geocode failures
        'confirmed', 
        'processing',
        'partially_shipped',
        'shipped', 
        'delivered', 
        'cancelled', 
        'refunded',
        'partially_refunded'
    ) NOT NULL DEFAULT 'cart',
    
    -- Financial details
    subtotal_amount DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    refunded_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    
    -- Fulfillment details
    fulfillment_warehouse_id INT NULL,
    is_split_shipment BOOLEAN NOT NULL DEFAULT FALSE,
    shipping_preference ENUM('standard', 'expedited', 'economy') NOT NULL DEFAULT 'standard',
    
    -- Shipping information (immutable snapshot)
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country CHAR(2),
    shipping_latitude DECIMAL(10,8),
    shipping_longitude DECIMAL(11,8),
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate'),
    geocode_requires_review BOOLEAN NOT NULL DEFAULT FALSE,  -- NEW: Flag for ops attention
    
    -- Billing information
    billing_address_line1 VARCHAR(255),
    billing_address_line2 VARCHAR(255),
    billing_city VARCHAR(100),
    billing_state VARCHAR(100),
    billing_postal_code VARCHAR(20),
    billing_country CHAR(2),
    
    -- Customer notes
    customer_notes TEXT,
    internal_notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    payment_confirmed_at TIMESTAMP NULL,
    shipped_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    cancelled_at TIMESTAMP NULL,
    
    -- Concurrency control
    version INT NOT NULL DEFAULT 1,
    
    -- Soft delete
    deleted_at TIMESTAMP NULL,
    
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    FOREIGN KEY (fulfillment_warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_customer_created (customer_id, created_at DESC),
    INDEX idx_status_created (status, created_at DESC),
    INDEX idx_order_number (order_number),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_customer_status (customer_id, status, created_at DESC),
    INDEX idx_status_updated (status, updated_at),
    INDEX idx_warehouse_status (fulfillment_warehouse_id, status, created_at),
    INDEX idx_deleted_at (deleted_at),
    INDEX idx_split_shipment (is_split_shipment, status),
    INDEX idx_shipping_preference (shipping_preference, status),
    INDEX idx_geocode_review (geocode_requires_review, status)  -- NEW: Ops queue
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED;

CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    warehouse_id INT NOT NULL,
    
    -- Immutable product snapshot
    product_sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    subtotal DECIMAL(10,2) NOT NULL,
    
    -- Refund tracking
    refunded_quantity INT NOT NULL DEFAULT 0,
    refunded_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    
    -- Shipment tracking
    shipment_id BIGINT NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_product_id (product_id),
    INDEX idx_warehouse_created (warehouse_id, created_at),
    INDEX idx_product_created (product_id, created_at),
    INDEX idx_shipment_id (shipment_id),
    
    CHECK (refunded_quantity <= quantity),
    CHECK (refunded_amount <= subtotal)
) ENGINE=InnoDB;

CREATE TABLE shipments (
    shipment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    warehouse_id INT NOT NULL,
    
    shipment_number VARCHAR(50) UNIQUE NOT NULL,
    carrier VARCHAR(100),
    tracking_number VARCHAR(255),
    tracking_url VARCHAR(500),
    
    status ENUM('pending', 'picked', 'packed', 'shipped', 'in_transit', 'delivered', 'failed') 
        NOT NULL DEFAULT 'pending',
    
    shipping_cost DECIMAL(10,2),
    estimated_delivery_date DATE,
    actual_delivery_date DATE,
    
    notification_sent BOOLEAN NOT NULL DEFAULT FALSE,
    notification_sent_at TIMESTAMP NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipped_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_warehouse_status (warehouse_id, status),
    INDEX idx_tracking_number (tracking_number),
    INDEX idx_status_created (status, created_at),
    INDEX idx_notification_status (notification_sent, status)
) ENGINE=InnoDB;

-- ============================================
-- PAYMENT SYSTEM WITH OPERATIONAL MONITORING
-- ============================================

CREATE TABLE payments (
    payment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    
    payment_gateway ENUM('stripe', 'paypal', 'square', 'adyen') NOT NULL,
    gateway_transaction_id VARCHAR(255),
    gateway_customer_id VARCHAR(255),
    
    payment_method ENUM('credit_card', 'debit_card', 'paypal', 'bank_transfer', 'crypto') NOT NULL,
    card_last_four CHAR(4),
    card_brand VARCHAR(20),
    
    amount DECIMAL(12,2) NOT NULL,
    currency_code CHAR(3) NOT NULL,
    
    status ENUM(
        'pending',
        'processing',
        'authorized',
        'captured',
        'failed',
        'cancelled',
        'refunded',
        'partially_refunded'
    ) NOT NULL DEFAULT 'pending',
    
    failure_code VARCHAR(50),
    failure_message TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    authorized_at TIMESTAMP NULL,
    captured_at TIMESTAMP NULL,
    failed_at TIMESTAMP NULL,
    refunded_at TIMESTAMP NULL,
    
    idempotency_key VARCHAR(255) UNIQUE,
    
    metadata JSON,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_gateway_transaction (payment_gateway, gateway_transaction_id),
    INDEX idx_status_created (status, created_at),
    INDEX idx_idempotency_key (idempotency_key),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_retry_count (retry_count, status)
) ENGINE=InnoDB;

CREATE TABLE payment_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_id BIGINT NOT NULL,
    
    event_type ENUM(
        'payment_initiated',
        'authorization_requested',
        'authorization_succeeded',
        'authorization_failed',
        'capture_requested',
        'capture_succeeded',
        'capture_failed',
        'refund_requested',
        'refund_succeeded',
        'refund_failed',
        'webhook_received',
        'retry_scheduled',
        'moved_to_dlq'
    ) NOT NULL,
    
    gateway_event_id VARCHAR(255),
    gateway_event_type VARCHAR(100),
    
    event_payload JSON,
    
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMP NULL,
    processing_error TEXT,
    retry_count INT NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMP NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE,
    
    UNIQUE KEY uk_gateway_event (gateway_event_id),
    INDEX idx_payment_created (payment_id, created_at DESC),
    INDEX idx_processed_created (processed, created_at),
    INDEX idx_event_type (event_type, created_at),
    INDEX idx_retry_schedule (processed, next_retry_at),
    INDEX idx_retry_count (retry_count, processed)
) ENGINE=InnoDB;

-- Error classification with manual grouping
CREATE TABLE payment_error_classes (
    class_id INT PRIMARY KEY AUTO_INCREMENT,
    class_name VARCHAR(100) UNIQUE NOT NULL,  -- e.g., 'stripe_timeout', 'insufficient_funds'
    event_type VARCHAR(50) NOT NULL,
    
    -- Match criteria (any field can be NULL for wildcard)
    gateway_pattern VARCHAR(100),  -- SQL LIKE pattern for gateway
    failure_code_pattern VARCHAR(100),  -- SQL LIKE pattern for failure_code
    message_keywords JSON,  -- Array of keywords that must appear in error message
    
    -- Auto-replay configuration
    auto_replay_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    auto_replay_delay_seconds INT NOT NULL DEFAULT 300,  -- 5 minutes default
    
    -- Learning metrics
    successful_replays INT NOT NULL DEFAULT 0,
    failed_replays INT NOT NULL DEFAULT 0,
    auto_replay_confidence DECIMAL(5,2) GENERATED ALWAYS AS (
        CASE 
            WHEN (successful_replays + failed_replays) > 0 
            THEN (successful_replays * 100.0) / (successful_replays + failed_replays)
            ELSE 0.0
        END
    ) STORED,
    
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_auto_replay (auto_replay_enabled, auto_replay_confidence),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB;

CREATE TABLE payment_events_dlq (
    dlq_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    original_event_id BIGINT NOT NULL,
    payment_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_payload JSON,
    failure_reason TEXT NOT NULL,
    error_class_id INT NULL,  -- NEW: Link to manually-curated error class
    retry_attempts INT NOT NULL,
    
    -- Operational workflow
    status ENUM('pending_classification', 'pending_review', 'investigating', 'auto_replay_scheduled', 'ready_for_replay', 'replayed', 'discarded') 
        NOT NULL DEFAULT 'pending_classification',
    assigned_to VARCHAR(100),
    priority ENUM('low', 'medium', 'high', 'critical') NOT NULL DEFAULT 'medium',
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP NULL,
    resolved_at TIMESTAMP NULL,
    replayed_at TIMESTAMP NULL,
    resolution_notes TEXT,
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (error_class_id) REFERENCES payment_error_classes(class_id),
    
    INDEX idx_payment_id (payment_id),
    INDEX idx_status_priority (status, priority, created_at),
    INDEX idx_assigned_to (assigned_to, status),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_resolved (resolved_at),
    INDEX idx_error_class (error_class_id, status)
) ENGINE=InnoDB;

CREATE TABLE dlq_metrics_daily (
    metric_date DATE PRIMARY KEY,
    total_entries INT NOT NULL DEFAULT 0,
    pending_classification INT NOT NULL DEFAULT 0,
    pending_review INT NOT NULL DEFAULT 0,
    investigating INT NOT NULL DEFAULT 0,
    auto_replay_scheduled INT NOT NULL DEFAULT 0,
    ready_for_replay INT NOT NULL DEFAULT 0,
    replayed_today INT NOT NULL DEFAULT 0,
    auto_replayed_today INT NOT NULL DEFAULT 0,
    discarded_today INT NOT NULL DEFAULT 0,
    avg_resolution_hours DECIMAL(8,2),
    critical_count INT NOT NULL DEFAULT 0,
    
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_metric_date (metric_date DESC)
) ENGINE=InnoDB;

CREATE TABLE refunds (
    refund_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_id BIGINT NOT NULL,
    order_id BIGINT NOT NULL,
    
    refund_amount DECIMAL(12,2) NOT NULL,
    refund_reason ENUM('customer_request', 'fraud', 'duplicate', 'product_issue', 'damaged', 'other') NOT NULL,
    refund_notes TEXT,
    
    gateway_refund_id VARCHAR(255),
    
    status ENUM('pending', 'processing', 'succeeded', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
    
    is_full_refund BOOLEAN NOT NULL DEFAULT TRUE,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    created_by VARCHAR(100),
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    
    INDEX idx_payment_id (payment_id),
    INDEX idx_order_id (order_id),
    INDEX idx_status_created (status, created_at),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_reason (refund_reason)
) ENGINE=InnoDB;

CREATE TABLE refund_items (
    refund_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    refund_id BIGINT NOT NULL,
    order_item_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    refund_amount DECIMAL(10,2) NOT NULL,
    restock BOOLEAN NOT NULL DEFAULT TRUE,
    restock_reason ENUM('resellable', 'damaged', 'customer_kept', 'other') NOT NULL DEFAULT 'resellable',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (refund_id) REFERENCES refunds(refund_id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id),
    
    INDEX idx_refund_id (refund_id),
    INDEX idx_order_item_id (order_item_id),
    INDEX idx_restock (restock, created_at),
    INDEX idx_restock_reason (restock_reason)
) ENGINE=InnoDB;

-- ============================================
-- AUDIT & HISTORY
-- ============================================

CREATE TABLE order_status_history (
    history_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    changed_by VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    
    INDEX idx_order_created (order_id, created_at DESC),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB;

-- ============================================
-- ARCHIVE SYSTEM WITH TIERED VERIFICATION
-- ============================================

CREATE TABLE order_archive_index (
    order_id BIGINT PRIMARY KEY,
    location ENUM('active', 'archived', 'cold_storage') NOT NULL DEFAULT 'active',
    archived_at TIMESTAMP NULL,
    cold_storage_path VARCHAR(500),
    
    -- Tiered verification strategy
    verification_tier ENUM('standard', 'high_value') NOT NULL DEFAULT 'standard',
    order_total DECIMAL(12,2),  -- Cached for tier determination
    
    last_verified_at TIMESTAMP NULL,
    verification_status ENUM('ok', 'missing', 'duplicate', 'inconsistent') NOT NULL DEFAULT 'ok',
    verification_checksum VARCHAR(64),
    
    INDEX idx_location (location),
    INDEX idx_archived_at (archived_at),
    INDEX idx_verification (verification_status, last_verified_at),
    INDEX idx_verification_tier (verification_tier)  -- NEW: Tier-based verification
) ENGINE=InnoDB;

CREATE TABLE orders_archive (
    LIKE orders
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED;

CREATE TABLE order_items_archive (
    LIKE order_items
) ENGINE=InnoDB;

CREATE TABLE order_status_history_archive (
    LIKE order_status_history
) ENGINE=InnoDB;

CREATE TABLE archive_batches (
    batch_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    archive_date DATE NOT NULL,
    orders_archived INT NOT NULL,
    oldest_order_date TIMESTAMP NOT NULL,
    newest_order_date TIMESTAMP NOT NULL,
    status ENUM('in_progress', 'completed', 'failed', 'verified') NOT NULL,
    
    -- Verification strategy applied
    verification_strategy ENUM('sampled', 'high_value_only', 'full') NOT NULL DEFAULT 'sampled',
    sample_percentage DECIMAL(5,2),  -- NULL for full verification
    high_value_orders_verified INT NOT NULL DEFAULT 0,
    sampled_orders_verified INT NOT NULL DEFAULT 0,
    
    verification_discrepancies INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    verified_at TIMESTAMP NULL,
    
    INDEX idx_archive_date (archive_date),
    INDEX idx_status (status),
    INDEX idx_verification (status, verified_at)
) ENGINE=InnoDB;

CREATE TABLE archive_reconciliation_log (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    batch_id BIGINT NULL,
    reconciliation_type ENUM('full_scan', 'batch_verification', 'spot_check', 'post_archive') NOT NULL,
    orders_checked INT NOT NULL,
    discrepancies_found INT NOT NULL,
    discrepancies_resolved INT NOT NULL,
    checksum_failures INT NOT NULL DEFAULT 0,
    execution_time_ms INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (batch_id) REFERENCES archive_batches(batch_id),
    
    INDEX idx_created_at (created_at DESC),
    INDEX idx_type_date (reconciliation_type, created_at)
) ENGINE=InnoDB;

-- ============================================
-- CAPACITY ALERTING & MONITORING
-- ============================================

CREATE TABLE capacity_alerts (
    alert_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    alert_type ENUM('warning', 'critical', 'overflow') NOT NULL,
    capacity_utilization DECIMAL(5,2) NOT NULL,  -- Percentage
    current_orders INT NOT NULL,
    effective_capacity INT NOT NULL,
    alert_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    notification_sent BOOLEAN NOT NULL DEFAULT FALSE,
    
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_warehouse_time (warehouse_id, alert_time DESC),
    INDEX idx_alert_type_time (alert_type, alert_time DESC),
    INDEX idx_resolved (resolved_at)
) ENGINE=InnoDB;
```

#### 2. Enhanced Multi-Warehouse Service

```python
from typing import List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime

@dataclass
class WarehouseAllocation:
    warehouse_id: int
    warehouse_code: str
    quantity: int
    distance_km: float
    shipping_cost: Decimal
    capacity_utilization: Decimal

@dataclass
class AllocationStrategy:
    shipping_preference: str
    prefer_single_warehouse: bool = True
    max_split_shipments: int = 2
    allow_capacity_overflow: bool = True
    
    @property
    def cost_weight(self) -> float:
        return {'economy': 0.9, 'standard': 0.7, 'expedited': 0.3}[self.shipping_preference]
    
    @property
    def speed_weight(self) -> float:
        return {'economy': 0.1, 'standard': 0.3, 'expedited': 0.7}[self.shipping_preference]

class MultiWarehouseInventoryService:
    
    # Configurable thresholds
    CAPACITY_WARNING_THRESHOLD = 0.80  # 80%
    CAPACITY_CRITICAL_THRESHOLD = 0.95  # 95%
    HIGH_VALUE_ORDER_THRESHOLD = Decimal('1000.00')
    
    async def reserve_stock_multi_warehouse(
        self,
        product_id: int,
        quantity: int,
        customer_id: int,
        shipping_address: Address,
        order_id: Optional[int] = None,
        ttl_seconds: int = 900,
        strategy: Optional[AllocationStrategy] = None
    ) -> List[WarehouseAllocation]:
        """Intelligently allocate stock with capacity handling."""
        if strategy is None:
            strategy = AllocationStrategy(
                shipping_preference='standard',
                allow_capacity_overflow=True
            )
        
        customer_coords = await self._get_cached_geocode(shipping_address, order_id)
        
        async with self.db.transaction():
            await self._reset_warehouse_capacity_if_needed()
            
            available_warehouses = await self._get_available_warehouses_with_capacity(
                product_id, quantity, date.today()
            )
            
            if not available_warehouses:
                raise InsufficientStockError(f"Product {product_id} out of stock")
            
            # Filter warehouses based on capacity policy
            if not strategy.allow_capacity_overflow:
                available_warehouses = [
                    wh for wh in available_warehouses
                    if wh['current_daily_orders'] < wh['effective_capacity']
                ]
                
                if not available_warehouses:
                    raise CapacityExceededError(
                        f"All warehouses at capacity. Retry later or enable overflow."
                    )
            
            warehouses_scored = await self._score_warehouses(
                available_warehouses,
                customer_coords,
                quantity,
                strategy
            )
            
            # Try single-warehouse fulfillment
            single_wh_options = [
                wh for wh in warehouses_scored 
                if wh['available_quantity'] >= quantity
            ]
            
            if single_wh_options:
                best_single = single_wh_options[0]
                
                split_allocation = self._calculate_split_allocation(
                    warehouses_scored, quantity, strategy
                )
                
                if self._should_prefer_single_warehouse(
                    best_single, split_allocation, strategy
                ):
                    allocations = await self._reserve_from_warehouse(
                        best_single, product_id, quantity, 
                        customer_id, order_id, ttl_seconds
                    )
                    await self._increment_warehouse_capacity(best_single['warehouse_id'])
                    await self._check_capacity_alert(best_single['warehouse_id'])
                    return allocations
            
            # Fall back to split shipment
            allocations = await self._reserve_split_shipment(
                warehouses_scored, product_id, quantity,
                customer_id, order_id, ttl_seconds,
                strategy.max_split_shipments
            )
            
            if sum(a.quantity for a in allocations) < quantity:
                raise InsufficientStockError(
                    f"Only {sum(a.quantity for a in allocations)}/{quantity} "
                    f"units available for product {product_id}"
                )
            
            for alloc in allocations:
                await self._increment_warehouse_capacity(alloc.warehouse_id)
                await self._check_capacity_alert(alloc.warehouse_id)
            
            return allocations
    
    async def _get_available_warehouses_with_capacity(
        self,
        product_id: int,
        quantity: int,
        check_date: date
    ) -> List[dict]:
        """
        Get warehouses with stock and effective capacity.
        
        Capacity resolution:
        1. Find all active overrides for check_date
        2. Select highest priority override (lowest priority number)
        3. Apply hard_capacity_limit if set, otherwise base * multiplier
        """
        return await self.db.execute(
            """
            WITH active_overrides AS (
                SELECT 
                    warehouse_id,
                    hard_capacity_limit,
                    capacity_multiplier,
                    priority,
                    reason,
                    ROW_NUMBER() OVER (
                        PARTITION BY warehouse_id 
                        ORDER BY priority ASC, created_at DESC
                    ) as rn
                FROM warehouse_capacity_overrides
                WHERE ? BETWEEN start_date AND end_date
            )
            SELECT 
                w.warehouse_id,
                w.warehouse_code,
                w.latitude,
                w.longitude,
                w.shipping_cost_base,
                w.priority,
                w.base_daily_capacity,
                w.current_daily_orders,
                wi.stock_quantity - wi.reserved_quantity as available_quantity,
                
                -- Calculate effective capacity (priority-based override resolution)
                COALESCE(
                    (SELECT hard_capacity_limit FROM active_overrides ao 
                     WHERE ao.warehouse_id = w.warehouse_id AND ao.rn = 1),
                    FLOOR(w.base_daily_capacity * COALESCE(
                        (SELECT capacity_multiplier FROM active_overrides ao 
                         WHERE ao.warehouse_id = w.warehouse_id AND ao.rn = 1),
                        1.0
                    ))
                ) as effective_capacity,
                
                (SELECT capacity_multiplier FROM active_overrides ao 
                 WHERE ao.warehouse_id = w.warehouse_id AND ao.rn = 1) as capacity_multiplier,
                
                (SELECT reason FROM active_overrides ao 
                 WHERE ao.warehouse_id = w.warehouse_id AND ao.rn = 1) as override_reason,
                
                -- Capacity utilization ratio
                CASE 
                    WHEN COALESCE(
                        (SELECT hard_capacity_limit FROM active_overrides ao 
                         WHERE ao.warehouse_id = w.warehouse_id AND ao.rn = 1),
                        w.base_daily_capacity
                    ) > 0
                    THEN w.current_daily_orders / COALESCE(
                        (SELECT hard_capacity_limit FROM active_overrides ao 
                         WHERE ao.warehouse_id = w.warehouse_id AND ao.rn = 1),
                        FLOOR(w.base_daily_capacity * COALESCE(
                            (SELECT capacity_multiplier FROM active_overrides ao 
                             WHERE ao.warehouse_id = w.warehouse_id AND ao.rn = 1),
                            1.0
                        ))
                    )
                    ELSE 0.0
                END as capacity_utilization
                
            FROM warehouses w
            JOIN warehouse_inventory wi 
                ON w.warehouse_id = wi.warehouse_id
            WHERE w.status = 'active'
                AND wi.product_id = ?
                AND (wi.stock_quantity - wi.reserved_quantity) > 0
            ORDER BY 
                capacity_utilization ASC,
                w.priority ASC
            """,
            (check_date, product_id)
        )
    
    async def _check_capacity_alert(self, warehouse_id: int):
        """Check capacity thresholds and create alerts if needed."""
        wh_stats = await self.db.execute(
            """
            SELECT 
                w.warehouse_id,
                w.current_daily_orders,
                w.base_daily_capacity,
                COALESCE(
                    (SELECT hard_capacity_limit 
                     FROM warehouse_capacity_overrides 
                     WHERE warehouse_id = w.warehouse_id 
                       AND CURDATE() BETWEEN start_date AND end_date
                     ORDER BY priority ASC, created_at DESC
                     LIMIT 1),
                    FLOOR(w.base_daily_capacity * COALESCE(
                        (SELECT capacity_multiplier 
                         FROM warehouse_capacity_overrides 
                         WHERE warehouse_id = w.warehouse_id 
                           AND CURDATE() BETWEEN start_date AND end_date
                         ORDER BY priority ASC, created_at DESC
                         LIMIT 1),
                        1.0
                    ))
                ) as effective_capacity
            FROM warehouses w
            WHERE w.warehouse_id = ?
            """,
            (warehouse_id,)
        )
        
        utilization = wh_stats.current_daily_orders / wh_stats.effective_capacity
        
        alert_type = None
        if utilization >= 1.0:
            alert_type = 'overflow'
        elif utilization >= self.CAPACITY_CRITICAL_THRESHOLD:
            alert_type = 'critical'
        elif utilization >= self.CAPACITY_WARNING_THRESHOLD:
            alert_type = 'warning'
        
        if alert_type:
            # Check if alert already exists and unresolved
            existing_alert = await self.db.execute(
                """
                SELECT alert_id FROM capacity_alerts
                WHERE warehouse_id = ? 
                  AND alert_type = ?
                  AND resolved_at IS NULL
                  AND alert_time > DATE_SUB(NOW(), INTERVAL 1 HOUR)
                """,
                (warehouse_id, alert_type)
            )
            
            if not existing_alert:
                await self.db.execute(
                    """
                    INSERT INTO capacity_alerts (
                        warehouse_id, alert_type, capacity_utilization,
                        current_orders, effective_capacity
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (warehouse_id, alert_type, utilization * 100,
                     wh_stats.current_daily_orders, wh_stats.effective_capacity)
                )
                
                # Send notification for critical/overflow
                if alert_type in ['critical', 'overflow']:
                    await self.alerting_service.send_alert(
                        severity=alert_type,
                        message=f"Warehouse {warehouse_id} at {utilization:.1%} capacity",
                        details={
                            'warehouse_id': warehouse_id,
                            'current_orders': wh_stats.current_daily_orders,
                            'effective_capacity': wh_stats.effective_capacity,
                            'utilization': f"{utilization:.1%}"
                        }
                    )
    
    async def _get_cached_geocode(
        self, 
        address: Address,
        order_id: Optional[int] = None
    ) -> Tuple[float, float]:
        """
        Geocode with three-tier lookup and failure handling.
        
        Lookup order:
        1. Redis cache (hot, <1ms)
        2. Database cache (warm, ~5ms)
        3. Reference table (pre-populated centroids)
        4. External API call (cold, ~200ms)
        5. Fallback to approximate centroid
        """
        cache_key = f"{address.postal_code}:{address.country}"
        
        # Tier 1: Redis
        cached = await self.redis.get(cache_key)
        if cached:
            return tuple(map(float, cached.split(',')))
        
        # Tier 2: Database cache
        db_cached = await self.db.execute(
            """
            UPDATE geocode_cache
            SET hit_count = hit_count + 1,
                last_accessed_at = NOW()
            WHERE postal_code = ? AND country = ?
            RETURNING latitude, longitude, geocode_quality
            """,
            (address.postal_code, address.country)
        )
        
        if db_cached:
            await self.redis.setex(cache_key, 86400, f"{db_cached.latitude},{db_cached.longitude}")
            return (db_cached.latitude, db_cached.longitude)
        
        # Tier 3: Reference table (pre-populated)
        reference = await self.db.execute(
            """
            SELECT latitude, longitude, geocode_quality
            FROM geocode_reference
            WHERE postal_code = ? AND country = ?
            """,
            (address.postal_code, address.country)
        )
        
        if reference:
            # Promote to cache
            await self.db.execute(
                """
                INSERT INTO geocode_cache (
                    postal_code, country, latitude, longitude,
                    geocode_quality, geocode_source
                )
                VALUES (?, ?, ?, ?, ?, 'reference_table')
                """,
                (address.postal_code, address.country, 
                 reference.latitude, reference.longitude, reference.geocode_quality)
            )
            await self.redis.setex(cache_key, 86400, f"{reference.latitude},{reference.longitude}")
            return (reference.latitude, reference.longitude)
        
        # Tier 4: External API
        try:
            coords, quality, source = await self.geocoding_service.geocode_with_quality(
                f"{address.line1}, {address.city}, {address.state} {address.postal_code}, {address.country}"
            )
            
            # Store in cache
            await self.db.execute(
                """
                INSERT INTO geocode_cache (
                    postal_code, country, latitude, longitude, 
                    geocode_quality, geocode_source
                )
                VALUES (?, ?, ?, ?, ?, 'api')
                """,
                (address.postal_code, address.country, coords[0], coords[1], quality)
            )
            
            await self.redis.setex(cache_key, 86400, f"{coords[0]},{coords[1]}")
            return coords
            
        except GeocodingError as e:
            # Tier 5: Fallback to approximate centroid
            await self._handle_geocode_failure(
                address, order_id, str(e), 'centroid'
            )
            
            # Use country-level centroid as last resort
            country_centroid = await self._get_country_centroid(address.country)
            
            await self.redis.setex(cache_key, 3600, f"{country_centroid[0]},{country_centroid[1]}")
            return country_centroid
    
    async def _handle_geocode_failure(
        self,
        address: Address,
        order_id: Optional[int],
        error_message: str,
        fallback_strategy: str
    ):
        """
        Log geocode failure and trigger customer notification workflow.
        """
        failure_id = await self.db.execute(
            """
            INSERT INTO geocode_failures (
                postal_code, country, full_address, order_id,
                failure_reason, fallback_strategy, resolution_status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (
                address.postal_code,
                address.country,
                f"{address.line1}, {address.city}, {address.state}",
                order_id,
                error_message,
                fallback_strategy
            )
        )
        
        if order_id:
            # Update order to require address review
            await self.db.execute(
                """
                UPDATE orders
                SET status = 'address_review',
                    geocode_requires_review = TRUE,
                    geocode_quality = 'approximate',
                    internal_notes = CONCAT(
                        COALESCE(internal_notes, ''),
                        '\nGeocoding failed (failure_id: ', ?, '). Customer notification required.'
                    )
                WHERE order_id = ?
                """,
                (failure_id, order_id)
            )
            
            # Trigger async customer notification
            await self.task_queue.enqueue(
                task='notify_customer_address_verification',
                args={
                    'order_id': order_id,
                    'failure_id': failure_id
                }
            )
    
    async def notify_customer_address_verification(self, order_id: int, failure_id: int):
        """
        Send customer email requesting address verification.
        
        Email includes:
        - Current address on file
        - Link to update shipping address
        - 48-hour deadline before order auto-cancels
        """
        order = await self.db.execute(
            "SELECT customer_id, order_number, shipping_address_line1, shipping_city, shipping_state, shipping_postal_code FROM orders WHERE order_id = ?",
            (order_id,)
        )
        
        customer = await self.db.execute(
            "SELECT email, first_name FROM customers WHERE customer_id = ?",
            (order.customer_id,)
        )
        
        verification_link = f"{self.config.base_url}/orders/{order.order_number}/verify-address?token={self._generate_verification_token(order_id)}"
        
        await self.email_service.send(
            to=customer.email,
            subject=f"Address verification needed for order {order.order_number}",
            template='address_verification',
            context={
                'customer_name': customer.first_name,
                'order_number': order.order_number,
                'address': f"{order.shipping_address_line1}, {order.shipping_city}, {order.shipping_state} {order.shipping_postal_code}",
                'verification_link': verification_link,
                'deadline_hours': 48
            }
        )
        
        await self.db.execute(
            """
            UPDATE geocode_failures
            SET customer_notified = TRUE,
                resolution_status = 'customer_contacted'
            WHERE failure_id = ?
            """,
            (failure_id,)
        )
        
        # Schedule auto-cancel job
        await self.task_queue.enqueue(
            task='auto_cancel_unverified_order',
            args={'order_id': order_id},
            execute_at=datetime.utcnow() + timedelta(hours=48)
        )
```

#### 3. Payment Service with Manual Error Classification

```python
from typing import Optional
import asyncio
from datetime import datetime, timedelta
from enum import Enum

class PaymentService:
    
    MAX_RETRY_ATTEMPTS = 5
    BASE_RETRY_DELAY = 30
    
    async def process_payment_event(self, event_id: int):
        """Process payment event with automatic retry and DLQ."""
        async with self.db.transaction():
            event = await self.db.execute(
                """
                SELECT 
                    pe.event_id,
                    pe.payment_id,
                    pe.event_type,
                    pe.event_payload,
                    pe.processed,
                    pe.retry_count,
                    p.order_id,
                    p.payment_gateway,
                    p.status as payment_status,
                    p.amount,
                    p.failure_code
                FROM payment_events pe
                JOIN payments p ON pe.payment_id = p.payment_id
                WHERE pe.event_id = ?
                FOR UPDATE
                """,
                (event_id,)
            )
            
            if not event or event.processed:
                return
            
            try:
                if event.event_type == 'authorization_succeeded':
                    await self._handle_authorization_success(event)
                elif event.event_type == 'capture_succeeded':
                    await self._handle_capture_success(event)
                elif event.event_type == 'authorization_failed':
                    await self._handle_authorization_failure(event)
                elif event.event_type == 'refund_succeeded':
                    await self._handle_refund_success(event)
                
                await self.db.execute(
                    """
                    UPDATE payment_events
                    SET processed = TRUE, processed_at = NOW()
                    WHERE event_id = ?
                    """,
                    (event_id,)
                )
                
            except Exception as e:
                await self._handle_event_failure(event, e)
                raise
    
    async def _handle_event_failure(self, event, error: Exception):
        """Handle failed event with DLQ routing and classification."""
        retry_count = event.retry_count + 1
        
        if retry_count >= self.MAX_RETRY_ATTEMPTS:
            # Check if error matches known class
            error_class = await self._classify_error(
                event.event_type,
                event.payment_gateway,
                event.failure_code,
                str(error)
            )
            
            priority = self._calculate_dlq_priority(event)
            
            # Determine initial status based on classification
            if error_class and error_class.auto_replay_enabled:
                initial_status = 'auto_replay_scheduled'
            elif error_class:
                initial_status = 'pending_review'
            else:
                initial_status = 'pending_classification'
            
            dlq_id = await self.db.execute(
                """
                INSERT INTO payment_events_dlq (
                    original_event_id,
                    payment_id,
                    event_type,
                    event_payload,
                    failure_reason,
                    error_class_id,
                    retry_attempts,
                    status,
                    priority
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event.event_id, event.payment_id, event.event_type,
                 event.event_payload, str(error), 
                 error_class.class_id if error_class else None,
                 retry_count, initial_status, priority)
            )
            
            await self.db.execute(
                """
                UPDATE payment_events
                SET event_type = 'moved_to_dlq',
                    processing_error = ?
                WHERE event_id = ?
                """,
                (f"Max retries exceeded: {error}", event.event_id)
            )
            
            await self._update_dlq_metrics()
            
            # Schedule auto-replay if enabled
            if error_class and error_class.auto_replay_enabled:
                await self._schedule_auto_replay(
                    dlq_id, 
                    error_class.class_id,
                    error_class.auto_replay_delay_seconds
                )
            elif priority in ['high', 'critical']:
                await self.alerting_service.send_alert(
                    severity=priority,
                    message=f"Payment event {event.event_id} moved to DLQ (needs classification)",
                    details={
                        'event_id': event.event_id,
                        'payment_id': event.payment_id,
                        'dlq_id': dlq_id,
                        'amount': event.amount,
                        'event_type': event.event_type,
                        'needs_classification': error_class is None
                    }
                )
        else:
            # Schedule retry
            delay = self._calculate_retry_delay(retry_count)
            next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            
            await self.db.execute(
                """
                UPDATE payment_events
                SET retry_count = ?,
                    next_retry_at = ?,
                    processing_error = ?
                WHERE event_id = ?
                """,
                (retry_count, next_retry_at, str(error), event.event_id)
            )
    
    async def _classify_error(
        self,
        event_type: str,
        gateway: str,
        failure_code: Optional[str],
        error_message: str
    ) -> Optional[dict]:
        """
        Match error against manually-curated error classes.
        
        Returns matching error class or None if unclassified.
        """
        error_classes = await self.db.execute(
            """
            SELECT 
                class_id, class_name, auto_replay_enabled,
                auto_replay_delay_seconds, auto_replay_confidence
            FROM payment_error_classes
            WHERE event_type = ?
            ORDER BY class_id
            """,
            (event_type,)
        )
        
        for error_class in error_classes:
            # Check gateway pattern
            if error_class.gateway_pattern:
                import re
                pattern = error_class.gateway_pattern.replace('%', '.*')
                if not re.match(pattern, gateway, re.IGNORECASE):
                    continue
            
            # Check failure code pattern
            if error_class.failure_code_pattern and failure_code:
                pattern = error_class.failure_code_pattern.replace('%', '.*')
                if not re.match(pattern, failure_code, re.IGNORECASE):
                    continue
            
            # Check message keywords
            if error_class.message_keywords:
                import json
                keywords = json.loads(error_class.message_keywords)
                if not all(kw.lower() in error_message.lower() for kw in keywords):
                    continue
            
            # Match found
            await self.db.execute(
                """
                UPDATE payment_error_classes
                SET last_seen_at = NOW()
                WHERE class_id = ?
                """,
                (error_class.class_id,)
            )
            
            return error_class
        
        return None
    
    async def create_error_class(
        self,
        class_name: str,
        event_type: str,
        gateway_pattern: Optional[str] = None,
        failure_code_pattern: Optional[str] = None,
        message_keywords: Optional[List[str]] = None,
        operator: str = 'system'
    ) -> int:
        """
        Manually create error class for DLQ categorization.
        
        Example:
        - class_name: 'stripe_timeout'
        - gateway_pattern: 'stripe'
        - message_keywords: ['timeout', 'connection']
        """
        import json
        
        class_id = await self.db.execute(
            """
            INSERT INTO payment_error_classes (
                class_name, event_type, gateway_pattern,
                failure_code_pattern, message_keywords, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (class_name, event_type, gateway_pattern, failure_code_pattern,
             json.dumps(message_keywords) if message_keywords else None, operator)
        )
        
        # Reclassify pending DLQ entries
        await self.task_queue.enqueue(
            task='reclassify_pending_dlq',
            args={'error_class_id': class_id}
        )
        
        return class_id
    
    async def enable_auto_replay_for_class(
        self,
        class_id: int,
        delay_seconds: int = 300,
        operator: str = 'system'
    ) -> bool:
        """
        Enable auto-replay for error class after validation.
        
        Requirements:
        - At least 10 successful manual replays
        - Success rate >= 85%
        """
        error_class = await self.db.execute(
            """
            SELECT 
                class_name, successful_replays, failed_replays,
                auto_replay_confidence
            FROM payment_error_classes
            WHERE class_id = ?
            """,
            (class_id,)
        )
        
        if not error_class:
            return False
        
        if error_class.successful_replays < 10:
            raise ValueError(
                f"Class '{error_class.class_name}' needs "
                f"{10 - error_class.successful_replays} more successful replays"
            )
        
        if error_class.auto_replay_confidence < 85.0:
            raise ValueError(
                f"Class confidence ({error_class.auto_replay_confidence:.1f}%) "
                f"below 85% threshold"
            )
        
        await self.db.execute(
            """
            UPDATE payment_error_classes
            SET auto_replay_enabled = TRUE,
                auto_replay_delay_seconds = ?
            WHERE class_id = ?
            """,
            (delay_seconds, class_id)
        )
        
        await self.logger.info(
            f"Auto-replay enabled for class {error_class.class_name} "
            f"by {operator} (confidence: {error_class.auto_replay_confidence:.1f}%)"
        )
        
        return True
    
    async def replay_dlq_entry(self, dlq_id: int, operator: str) -> dict:
        """Manual replay with learning feedback."""
        async with self.db.transaction():
            dlq_entry = await self.db.execute(
                """
                SELECT 
                    dlq_id, original_event_id, payment_id,
                    event_type, event_payload, status, error_class_id
                FROM payment_events_dlq
                WHERE dlq_id = ?
                FOR UPDATE
                """,
                (dlq_id,)
            )
            
            if not dlq_entry or dlq_entry.status not in ['ready_for_replay', 'pending_review']:
                return {'success': False, 'reason': 'invalid_status'}
            
            try:
                new_event_id = await self.db.execute(
                    """
                    INSERT INTO payment_events (
                        payment_id, event_type, event_payload, processed
                    )
                    VALUES (?, ?, ?, FALSE)
                    """,
                    (dlq_entry.payment_id, dlq_entry.event_type, dlq_entry.event_payload)
                )
                
                await self.process_payment_event(new_event_id)
                
                await self.db.execute(
                    """
                    UPDATE payment_events_dlq
                    SET status = 'replayed',
                        replayed_at = NOW(),
                        resolution_notes = ?
                    WHERE dlq_id = ?
                    """,
                    (f"Manually replayed by {operator}", dlq_id)
                )
                
                # Update error class learning
                if dlq_entry.error_class_id:
                    await self.db.execute(
                        """
                        UPDATE payment_error_classes
                        SET successful_replays = successful_replays + 1
                        WHERE class_id = ?
                        """,
                        (dlq_entry.error_class_id,)
                    )
                    
                    # Check if qualifies for auto-replay
                    updated_class = await self.db.execute(
                        """
                        SELECT 
                            class_name, successful_replays, 
                            auto_replay_confidence, auto_replay_enabled
                        FROM payment_error_classes
                        WHERE class_id = ?
                        """,
                        (dlq_entry.error_class_id,)
                    )
                    
                    if (not updated_class.auto_replay_enabled and
                        updated_class.successful_replays >= 10 and
                        updated_class.auto_replay_confidence >= 85.0):
                        return {
                            'success': True,
                            'ready_for_auto_replay': True,
                            'class_name': updated_class.class_name,
                            'confidence': updated_class.auto_replay_confidence
                        }
                
                return {'success': True}
                
            except Exception as e:
                await self.db.execute(
                    """
                    UPDATE payment_events_dlq
                    SET resolution_notes = CONCAT(
                        COALESCE(resolution_notes, ''),
                        '\nReplay failed (', ?, '): ', ?
                    )
                    WHERE dlq_id = ?
                    """,
                    (operator, str(e), dlq_id)
                )
                
                # Update error class failure
                if dlq_entry.error_class_id:
                    await self.db.execute(
                        """
                        UPDATE payment_error_classes
                        SET failed_replays = failed_replays + 1
                        WHERE class_id = ?
                        """,
                        (dlq_entry.error_class_id,)
                    )
                
                return {'success': False, 'error': str(e)}
```

#### 4. Archive Service with Tiered Verification

```python
class OrderArchiveService:
    
    HIGH_VALUE_THRESHOLD = Decimal('1000.00')
    STANDARD_SAMPLE_RATE = 0.10  # 10% sampling for standard orders
    
    async def archive_old_orders(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000,
        verification_strategy: str = 'sampled'
    ) -> int:
        """
        Archive with configurable verification strategy.
        
        Strategies:
        - 'sampled': 10% random sample + all high-value orders
        - 'high_value_only': Only verify orders >= $1000
        - 'full': Verify every order (slow, high integrity)
        """
        terminal_states = ['delivered', 'cancelled', 'refunded', 'partially_refunded']
        total_archived = 0
        
        batch_id = await self._create_archive_batch(cutoff_date, verification_strategy)
        
        try:
            while True:
                async with self.db.transaction():
                    orders = await self.db.execute(
                        """
                        SELECT order_id, total_amount
                        FROM orders
                        WHERE created_at < ?
                            AND status IN (?, ?, ?, ?)
                            AND deleted_at IS NULL
                        LIMIT ?
                        FOR UPDATE SKIP LOCKED
                        """,
                        (cutoff_date, *terminal_states, batch_size)
                    )
                    
                    if not orders:
                        break
                    
                    order_ids = [o.order_id for o in orders]
                    
                    # Copy to archive
                    await self._copy_to_archive(order_ids)
                    
                    # Determine verification tier and checksum
                    for order in orders:
                        is_high_value = order.total_amount >= self.HIGH_VALUE_THRESHOLD
                        verification_tier = 'high_value' if is_high_value else 'standard'
                        
                        # Calculate checksum based on strategy
                        should_verify = (
                            verification_strategy == 'full' or
                            (verification_strategy == 'high_value_only' and is_high_value) or
                            (verification_strategy == 'sampled' and 
                             (is_high_value or self._should_sample()))
                        )
                        
                        checksum = None
                        if should_verify:
                            checksum = await self._calculate_order_checksum(order.order_id)
                        
                        await self.db.execute(
                            """
                            INSERT INTO order_archive_index (
                                order_id, location, archived_at,
                                verification_tier, order_total,
                                last_verified_at, verification_checksum,
                                verification_status
                            )
                            VALUES (?, 'archived', NOW(), ?, ?, ?, ?, 'ok')
                            ON DUPLICATE KEY UPDATE 
                                location = 'archived',
                                archived_at = NOW(),
                                last_verified_at = IF(? IS NOT NULL, NOW(), last_verified_at),
                                verification_checksum = COALESCE(?, verification_checksum),
                                verification_status = 'ok'
                            """,
                            (order.order_id, verification_tier, order.total_amount,
                             checksum if should_verify else None,
                             checksum,
                             should_verify, checksum)
                        )
                    
                    # Soft delete from main table
                    await self.db.execute(
                        """
                        UPDATE orders
                        SET deleted_at = NOW()
                        WHERE order_id IN ({})
                        """.format(','.join('?' * len(order_ids))),
                        order_ids
                    )
                    
                    total_archived += len(order_ids)
                    await self._update_batch_progress(batch_id, total_archived)
                
                await asyncio.sleep(0.5)
            
            await self._complete_batch(batch_id)
            
            # Post-archive verification
            await self.verify_archive_batch(batch_id, verification_strategy)
            
            return total_archived
            
        except Exception as e:
            await self._fail_batch(batch_id)
            raise
    
    def _should_sample(self) -> bool:
        """Random sampling for standard orders."""
        import random
        return random.random() < self.STANDARD_SAMPLE_RATE
    
    async def verify_archive_batch(
        self,
        batch_id: int,
        strategy: str
    ) -> dict:
        """
        Verify archive batch with tiered approach.
        """
        start_time = datetime.utcnow()
        
        batch = await self.db.execute(
            "SELECT orders_archived FROM archive_batches WHERE batch_id = ?",
            (batch_id,)
        )
        
        # Get orders to verify based on strategy
        if strategy == 'full':
            orders_to_verify = await self.db.execute(
                """
                SELECT order_id, verification_checksum
                FROM order_archive_index
                WHERE archived_at >= (SELECT created_at FROM archive_batches WHERE batch_id = ?)
                  AND archived_at <= (SELECT completed_at FROM archive_batches WHERE batch_id = ?)
                """,
                (batch_id, batch_id)
            )
        elif strategy == 'high_value_only':
            orders_to_verify = await self.db.execute(
                """
                SELECT order_id, verification_checksum
                FROM order_archive_index
                WHERE archived_at >= (SELECT created_at FROM archive_batches WHERE batch_id = ?)
                  AND archived_at <= (SELECT completed_at FROM archive_batches WHERE batch_id = ?)
                  AND verification_tier = 'high_value'
                """,
                (batch_id, batch_id)
            )
        else:  # sampled
            orders_to_verify = await self.db.execute(
                """
                SELECT order_id, verification_checksum
                FROM order_archive_index
                WHERE archived_at >= (SELECT created_at FROM archive_batches WHERE batch_id = ?)
                  AND archived_at <= (SELECT completed_at FROM archive_batches WHERE batch_id = ?)
                  AND verification_checksum IS NOT NULL
                """,
                (batch_id, batch_id)
            )
        
        discrepancies = 0
        checksum_failures = 0
        high_value_verified = 0
        
        for entry in orders_to_verify:
            # Count high-value verifications
            tier = await self.db.execute(
                "SELECT verification_tier FROM order_archive_index WHERE order_id = ?",
                (entry.order_id,)
            )
            if tier.verification_tier == 'high_value':
                high_value_verified += 1
            
            # Check archive exists
            archived = await self.db.execute(
                "SELECT 1 FROM orders_archive WHERE order_id = ?",
                (entry.order_id,)
            )
            
            if not archived:
                discrepancies += 1
                await self._mark_index_inconsistent(entry.order_id, 'missing_from_archive')
                continue
            
            # Check removed from active
            active = await self.db.execute(
                "SELECT 1 FROM orders WHERE order_id = ? AND deleted_at IS NULL",
                (entry.order_id,)
            )
            
            if active:
                discrepancies += 1
                await self._mark_index_inconsistent(entry.order_id, 'still_in_active')
                continue
            
            # Verify checksum if present
            if entry.verification_checksum:
                archived_checksum = await self._calculate_archived_order_checksum(entry.order_id)
                if archived_checksum != entry.verification_checksum:
                    discrepancies += 1
                    checksum_failures += 1
                    await self._mark_index_inconsistent(entry.order_id, 'checksum_mismatch')
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        # Log reconciliation
        await self.db.execute(
            """
            INSERT INTO archive_reconciliation_log (
                batch_id, reconciliation_type, orders_checked,
                discrepancies_found, discrepancies_resolved,
                checksum_failures, execution_time_ms
            )
            VALUES (?, 'post_archive', ?, ?, 0, ?, ?)
            """,
            (batch_id, len(orders_to_verify), discrepancies, checksum_failures, execution_time_ms)
        )
        
        # Update batch with verification details
        sample_pct = None
        if strategy == 'sampled' and batch.orders_archived > 0:
            sample_pct = (len(orders_to_verify) / batch.orders_archived) * 100
        
        if discrepancies == 0:
            await self.db.execute(
                """
                UPDATE archive_batches
                SET status = 'verified',
                    verified_at = NOW(),
                    verification_discrepancies = 0,
                    verification_strategy = ?,
                    sample_percentage = ?,
                    high_value_orders_verified = ?
                WHERE batch_id = ?
                """,
                (strategy, sample_pct, high_value_verified, batch_id)
            )
        else:
            await self.db.execute(
                """
                UPDATE archive_batches
                SET verification_discrepancies = ?,
                    verification_strategy = ?,
                    sample_percentage = ?,
                    high_value_orders_verified = ?
                WHERE batch_id = ?
                """,
                (discrepancies, strategy, sample_pct, high_value_verified, batch_id)
            )
            
            # Alert if significant issues
            error_rate = discrepancies / len(orders_to_verify) if orders_to_verify else 0
            if error_rate > 0.01:  # >1% error rate
                await self.alerting_service.send_alert(
                    severity='high',
                    message=f"Archive batch {batch_id} verification failed",
                    details={
                        'batch_id': batch_id,
                        'discrepancies': discrepancies,
                        'checksum_failures': checksum_failures,
                        'orders_checked': len(orders_to_verify),
                        'error_rate': f"{error_rate:.2%}"
                    }
                )
        
        return {
            'orders_checked': len(orders_to_verify),
            'discrepancies_found': discrepancies,
            'checksum_failures': checksum_failures,
            'high_value_orders_verified': high_value_verified,
            'execution_time_ms': execution_time_ms
        }
    
    async def _calculate_order_checksum(self, order_id: int) -> str:
        """Calculate SHA256 checksum of order data."""
        order_data = await self.db.execute(
            """
            SELECT o.*, 
                   GROUP_CONCAT(oi.order_item_id ORDER BY oi.order_item_id) as items
            FROM orders o
            LEFT JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_id = ?
            GROUP BY o.order_id
            """,
            (order_id,)
        )
        
        import json
        import hashlib
        serialized = json.dumps(dict(order_data), sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
```