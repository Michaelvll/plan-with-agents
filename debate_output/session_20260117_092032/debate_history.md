# Claude Code Debate Session

**Started:** 2026-01-17T09:20:32.095237
**Ended:** 2026-01-17T09:46:58.744679
**Status:** debating
**Rounds:** 4

## Initial Prompt

Design schema for e-commerce orders with indexing strategy

Requirements:
- Support for orders, order items, customers, products
- Handle order status transitions
- Efficient queries for common operations
- Consider read vs write optimization
- Plan for future scale

---

## Round 1

### 🔵 Agent A

## Design

### E-Commerce Order System - Database Schema & Indexing Strategy

#### 1. Core Data Models

```sql
-- Customers Table
CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'suspended', 'deleted') NOT NULL DEFAULT 'active',
    
    INDEX idx_email (email),
    INDEX idx_status_created (status, created_at)
) ENGINE=InnoDB;

-- Products Table
CREATE TABLE products (
    product_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    status ENUM('active', 'inactive', 'discontinued') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_sku (sku),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- Orders Table (Optimized for read-heavy operations)
CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    status ENUM('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') NOT NULL DEFAULT 'pending',
    total_amount DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    
    -- Shipping information (denormalized for read performance)
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country VARCHAR(2),
    
    -- Billing information
    billing_address_line1 VARCHAR(255),
    billing_address_line2 VARCHAR(255),
    billing_city VARCHAR(100),
    billing_state VARCHAR(100),
    billing_postal_code VARCHAR(20),
    billing_country VARCHAR(2),
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP NULL,
    shipped_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    
    -- Critical indexes for common queries
    INDEX idx_customer_created (customer_id, created_at DESC),
    INDEX idx_status_created (status, created_at DESC),
    INDEX idx_order_number (order_number),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_customer_status (customer_id, status)
) ENGINE=InnoDB;

-- Order Items Table
CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    
    -- Denormalized product info (snapshot at order time)
    product_sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_product_id (product_id)
) ENGINE=InnoDB;

-- Order Status History (Audit trail)
CREATE TABLE order_status_history (
    history_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    from_status VARCHAR(50),
    to_status VARCHAR(50) NOT NULL,
    changed_by VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    
    INDEX idx_order_created (order_id, created_at DESC)
) ENGINE=InnoDB;
```

#### 2. Architecture Components

**a) Data Access Layer**
```python
class OrderRepository:
    """Handles all order-related database operations"""
    
    async def create_order(self, order_data: OrderCreate) -> Order:
        """Create order with items in a transaction"""
        pass
    
    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """Retrieve order with items"""
        pass
    
    async def get_customer_orders(
        self, 
        customer_id: int, 
        limit: int = 20,
        offset: int = 0,
        status_filter: Optional[List[str]] = None
    ) -> List[Order]:
        """Get paginated customer orders with optional status filter"""
        pass
    
    async def update_order_status(
        self, 
        order_id: int, 
        new_status: str,
        user: str
    ) -> bool:
        """Update status and record history"""
        pass
```

**b) Caching Strategy**
```python
# Redis cache keys design
CACHE_KEYS = {
    'order': 'order:{order_id}',  # TTL: 5 minutes
    'customer_orders': 'customer:{customer_id}:orders:{page}',  # TTL: 2 minutes
    'order_stats': 'stats:orders:{date}',  # TTL: 1 hour
}
```

#### 3. Indexing Strategy Rationale

**Primary Indexes:**
- `idx_customer_created (customer_id, created_at DESC)`: Most common query - customer viewing their order history
- `idx_status_created (status, created_at DESC)`: Admin dashboard filtering by status
- `idx_order_number`: Order lookup by order number (customer service)

**Composite Index Benefits:**
- Covering indexes reduce need to access table data
- Sorted DESC for created_at matches common "newest first" queries
- Customer_id + status composite enables efficient filtering

**Trade-offs:**
- More indexes = slower writes, but acceptable for read-heavy e-commerce
- Denormalized shipping/billing addresses slightly increase storage but dramatically improve read performance
- Order items cascade delete ensures data consistency

#### 4. Query Optimization Examples

```sql
-- Query 1: Customer order history (uses idx_customer_created)
SELECT order_id, order_number, status, total_amount, created_at
FROM orders
WHERE customer_id = ? AND status != 'cancelled'
ORDER BY created_at DESC
LIMIT 20;

-- Query 2: Recent pending orders (uses idx_status_created)
SELECT order_id, customer_id, total_amount, created_at
FROM orders
WHERE status = 'pending' AND created_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
ORDER BY created_at DESC;

-- Query 3: Order details with items (uses primary keys + idx_order_id)
SELECT o.*, oi.product_name, oi.quantity, oi.unit_price
FROM orders o
INNER JOIN order_items oi ON o.order_id = oi.order_id
WHERE o.order_id = ?;
```

#### 5. Scaling Strategy

**Horizontal Partitioning (Future):**
```sql
-- Partition orders by date range
ALTER TABLE orders PARTITION BY RANGE (YEAR(created_at)) (
    PARTITION p2023 VALUES LESS THAN (2024),
    PARTITION p2024 VALUES LESS THAN (2025),
    PARTITION p2025 VALUES LESS THAN (2026),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
```

**Read Replicas:**
- Master: Handles all writes
- Read replicas (2+): Handle customer-facing queries
- Analytics replica: Separate for reporting queries

**Sharding Strategy (10M+ orders):**
- Shard by customer_id hash
- Maintains locality for customer queries
- Order lookup requires distributed query or mapping table

#### 6. Error Handling & Constraints

**Data Integrity:**
- Foreign key constraints ensure referential integrity
- Transactions for multi-table operations (order + items)
- Optimistic locking via updated_at for concurrent updates

**Application-Level Validations:**
```python
class OrderStatusTransition:
    """Valid state transitions"""
    VALID_TRANSITIONS = {
        'pending': ['confirmed', 'cancelled'],
        'confirmed': ['processing', 'cancelled'],
        'processing': ['shipped', 'cancelled'],
        'shipped': ['delivered'],
        'delivered': ['refunded'],
        'cancelled': [],
        'refunded': []
    }
    
    @staticmethod
    def is_valid_transition(from_status: str, to_status: str) -> bool:
        return to_status in VALID_TRANSITIONS.get(from_status, [])
```

**Error Scenarios:**
- Invalid status transition: Reject with 400 error
- Insufficient stock: Reject order creation with specific error
- Duplicate order_number: Database constraint prevents
- Missing customer: Foreign key constraint prevents

## Rationale

**Why denormalize addresses in orders table?**
- Order queries are 10-100x more frequent than order creation
- Historical address data must be immutable (customer may change address)
- Eliminates JOIN overhead on most common queries

**Why separate order_status_history table?**
- Audit trail without bloating main orders table
- Enables compliance requirements (track who changed what)
- History queries are rare and can tolerate slower performance

**Why ENUM for status fields?**
- Enforces valid values at database level
- More efficient storage than VARCHAR
- Clear contract for application developers

**Why composite indexes instead of single-column?**
- MySQL can use leftmost prefix of composite index
- Eliminates need for separate single-column indexes
- Directly supports WHERE + ORDER BY patterns

## What I Changed

This is the initial design proposal (Round 1).

## What I Kept

N/A - Initial proposal

## Open Questions

1. **Soft delete vs hard delete**: Should cancelled/deleted orders be retained indefinitely or archived?
2. **Payment information**: Not included - should this be separate service or integrated?
3. **Inventory locking**: Should order creation lock product stock optimistically or pessimistically?
4. **International considerations**: Should we support multiple currencies per order?

## Convergence Status

**ITERATING** - This is the first iteration and needs critical review for weaknesses.

## PROMPT_FOR_CRITIC:

Focus on identifying potential bottlenecks in the indexing strategy and whether the denormalization approach creates data consistency risks. Also evaluate if the schema can handle high-concurrency scenarios during flash sales or peak traffic periods.

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

### E-Commerce Order System - High-Concurrency Database Schema & Indexing Strategy

#### 1. Core Data Models with Optimistic Locking

```sql
-- Customers Table
CREATE TABLE customers (
    customer_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(50),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    status ENUM('active', 'suspended', 'deleted') NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,  -- Optimistic locking
    
    INDEX idx_email (email),
    INDEX idx_status_created (status, created_at)
) ENGINE=InnoDB;

-- Products Table with Stock Management
CREATE TABLE products (
    product_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    reserved_quantity INT NOT NULL DEFAULT 0,  -- For in-progress orders
    status ENUM('active', 'inactive', 'discontinued') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    version INT NOT NULL DEFAULT 1,  -- Optimistic locking for stock updates
    
    INDEX idx_sku (sku),
    INDEX idx_status (status),
    CHECK (stock_quantity >= 0),
    CHECK (reserved_quantity >= 0),
    CHECK (reserved_quantity <= stock_quantity)
) ENGINE=InnoDB;

-- Orders Table (Optimized for read-heavy operations)
CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    status ENUM('cart', 'pending_payment', 'payment_failed', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled', 'refunded') NOT NULL DEFAULT 'cart',
    total_amount DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',  -- ISO 4217
    
    -- Shipping information (denormalized snapshot)
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country CHAR(2),  -- ISO 3166-1 alpha-2
    
    -- Billing information
    billing_address_line1 VARCHAR(255),
    billing_address_line2 VARCHAR(255),
    billing_city VARCHAR(100),
    billing_state VARCHAR(100),
    billing_postal_code VARCHAR(20),
    billing_country CHAR(2),
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    payment_confirmed_at TIMESTAMP NULL,
    shipped_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    cancelled_at TIMESTAMP NULL,
    
    -- Concurrency control
    version INT NOT NULL DEFAULT 1,  -- Optimistic locking
    
    -- Soft delete
    deleted_at TIMESTAMP NULL,
    
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    
    -- Critical indexes for common queries
    INDEX idx_customer_created (customer_id, created_at DESC),
    INDEX idx_status_created (status, created_at DESC),
    INDEX idx_order_number (order_number),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_customer_status (customer_id, status, created_at DESC),
    -- For cleanup jobs and analytics
    INDEX idx_status_updated (status, updated_at),
    -- Soft delete aware queries
    INDEX idx_deleted_at (deleted_at)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED;  -- Compression for historical data

-- Order Items Table
CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    
    -- Denormalized product info (immutable snapshot at order time)
    product_sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    subtotal DECIMAL(10,2) NOT NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_product_id (product_id),
    -- For inventory analysis
    INDEX idx_product_created (product_id, created_at)
) ENGINE=InnoDB;

-- Order Status History (Audit trail)
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
    -- For compliance and analytics
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB;

-- Inventory Reservations (Critical for flash sales)
CREATE TABLE inventory_reservations (
    reservation_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    order_id BIGINT NULL,  -- NULL for cart reservations
    customer_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    status ENUM('active', 'expired', 'completed', 'cancelled') NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP NOT NULL,  -- Auto-release after timeout
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    
    -- Critical for cleanup jobs
    INDEX idx_status_expires (status, expires_at),
    INDEX idx_product_status (product_id, status),
    INDEX idx_order_id (order_id),
    INDEX idx_customer_created (customer_id, created_at)
) ENGINE=InnoDB;
```

#### 2. High-Concurrency Data Access Layer

```python
from typing import Optional, List
from contextlib import asynccontextmanager
import asyncio

class InventoryService:
    """Handles stock management with pessimistic locking for writes"""
    
    async def reserve_stock(
        self, 
        product_id: int, 
        quantity: int,
        customer_id: int,
        order_id: Optional[int] = None,
        ttl_seconds: int = 900  # 15 minutes default
    ) -> Optional[int]:
        """
        Reserve stock with two-phase approach:
        1. Pessimistic lock on product row
        2. Create reservation record
        3. Update reserved_quantity
        
        Returns reservation_id if successful, None if insufficient stock
        """
        async with self.db.transaction():
            # SELECT FOR UPDATE prevents race conditions
            product = await self.db.execute(
                """
                SELECT product_id, stock_quantity, reserved_quantity, version
                FROM products
                WHERE product_id = ? AND status = 'active'
                FOR UPDATE
                """,
                (product_id,)
            )
            
            if not product:
                return None
            
            available = product.stock_quantity - product.reserved_quantity
            if available < quantity:
                return None
            
            # Create reservation with expiry
            expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
            reservation_id = await self.db.execute(
                """
                INSERT INTO inventory_reservations 
                (product_id, order_id, customer_id, quantity, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (product_id, order_id, customer_id, quantity, expires_at)
            )
            
            # Update reserved quantity with optimistic lock check
            updated = await self.db.execute(
                """
                UPDATE products
                SET reserved_quantity = reserved_quantity + ?,
                    version = version + 1
                WHERE product_id = ? AND version = ?
                """,
                (quantity, product_id, product.version)
            )
            
            if updated == 0:
                raise ConcurrencyError("Product was modified by another transaction")
            
            return reservation_id
    
    async def release_reservation(self, reservation_id: int) -> bool:
        """Release stock reservation (timeout or cancellation)"""
        async with self.db.transaction():
            reservation = await self.db.execute(
                """
                SELECT product_id, quantity, status
                FROM inventory_reservations
                WHERE reservation_id = ?
                FOR UPDATE
                """,
                (reservation_id,)
            )
            
            if not reservation or reservation.status != 'active':
                return False
            
            # Mark reservation as cancelled
            await self.db.execute(
                """
                UPDATE inventory_reservations
                SET status = 'cancelled'
                WHERE reservation_id = ?
                """,
                (reservation_id,)
            )
            
            # Release reserved quantity
            await self.db.execute(
                """
                UPDATE products
                SET reserved_quantity = GREATEST(0, reserved_quantity - ?)
                WHERE product_id = ?
                """,
                (reservation.quantity, reservation.product_id)
            )
            
            return True
    
    async def confirm_reservation(self, reservation_id: int) -> bool:
        """Convert reservation to actual sale (order confirmed)"""
        async with self.db.transaction():
            reservation = await self.db.execute(
                """
                SELECT product_id, quantity, status
                FROM inventory_reservations
                WHERE reservation_id = ?
                FOR UPDATE
                """,
                (reservation_id,)
            )
            
            if not reservation or reservation.status != 'active':
                return False
            
            # Mark reservation as completed
            await self.db.execute(
                """
                UPDATE inventory_reservations
                SET status = 'completed'
                WHERE reservation_id = ?
                """,
                (reservation_id,)
            )
            
            # Deduct from both stock and reserved
            await self.db.execute(
                """
                UPDATE products
                SET stock_quantity = stock_quantity - ?,
                    reserved_quantity = GREATEST(0, reserved_quantity - ?)
                WHERE product_id = ?
                """,
                (reservation.quantity, reservation.quantity, reservation.product_id)
            )
            
            return True


class OrderRepository:
    """Handles all order-related database operations"""
    
    def __init__(self, db, cache, inventory_service: InventoryService):
        self.db = db
        self.cache = cache
        self.inventory = inventory_service
    
    async def create_order(
        self, 
        customer_id: int,
        items: List[OrderItemCreate],
        shipping_address: Address,
        billing_address: Address
    ) -> Order:
        """
        Create order with inventory reservation in transaction
        
        Flow:
        1. Create order record in 'cart' status
        2. Reserve inventory for each item
        3. Create order_items records
        4. Transition to 'pending_payment'
        """
        async with self.db.transaction():
            # Generate unique order number
            order_number = await self._generate_order_number()
            
            # Create order in cart status
            order_id = await self.db.execute(
                """
                INSERT INTO orders (
                    customer_id, order_number, status,
                    total_amount, shipping_address_line1, ...
                )
                VALUES (?, ?, 'cart', ?, ?, ...)
                """,
                (customer_id, order_number, total_amount, ...)
            )
            
            # Reserve inventory for each item
            reservations = []
            for item in items:
                reservation_id = await self.inventory.reserve_stock(
                    product_id=item.product_id,
                    quantity=item.quantity,
                    customer_id=customer_id,
                    order_id=order_id,
                    ttl_seconds=1800  # 30 minutes for payment
                )
                
                if not reservation_id:
                    # Rollback entire transaction
                    raise InsufficientStockError(
                        f"Product {item.product_id} has insufficient stock"
                    )
                
                reservations.append(reservation_id)
            
            # Create order items
            for item in items:
                await self.db.execute(
                    """
                    INSERT INTO order_items (
                        order_id, product_id, product_sku, product_name,
                        unit_price, quantity, subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (order_id, item.product_id, item.sku, item.name,
                     item.price, item.quantity, item.subtotal)
                )
            
            # Transition to pending_payment
            await self._update_order_status(
                order_id, 'cart', 'pending_payment', 'system'
            )
            
            # Invalidate customer orders cache
            await self.cache.delete(f'customer:{customer_id}:orders:*')
            
            return await self.get_order_by_id(order_id)
    
    async def confirm_payment(self, order_id: int) -> bool:
        """
        Confirm payment and convert reservations to sales
        """
        async with self.db.transaction():
            order = await self.db.execute(
                """
                SELECT order_id, customer_id, status, version
                FROM orders
                WHERE order_id = ?
                FOR UPDATE
                """,
                (order_id,)
            )
            
            if not order or order.status != 'pending_payment':
                return False
            
            # Get all reservations for this order
            reservations = await self.db.execute(
                """
                SELECT reservation_id
                FROM inventory_reservations
                WHERE order_id = ? AND status = 'active'
                """,
                (order_id,)
            )
            
            # Confirm all reservations (deduct stock)
            for reservation in reservations:
                await self.inventory.confirm_reservation(reservation.reservation_id)
            
            # Update order status with optimistic lock
            updated = await self.db.execute(
                """
                UPDATE orders
                SET status = 'confirmed',
                    payment_confirmed_at = NOW(),
                    version = version + 1
                WHERE order_id = ? AND version = ?
                """,
                (order_id, order.version)
            )
            
            if updated == 0:
                raise ConcurrencyError("Order was modified by another transaction")
            
            # Record status change
            await self._record_status_change(
                order_id, 'pending_payment', 'confirmed', 'payment_service'
            )
            
            # Invalidate cache
            await self.cache.delete(f'order:{order_id}')
            await self.cache.delete(f'customer:{order.customer_id}:orders:*')
            
            return True
    
    async def get_order_by_id(self, order_id: int) -> Optional[Order]:
        """Retrieve order with items (cache-aside pattern)"""
        # Try cache first
        cached = await self.cache.get(f'order:{order_id}')
        if cached:
            return Order.parse_raw(cached)
        
        # Query database
        order = await self.db.execute(
            """
            SELECT o.*, 
                   JSON_ARRAYAGG(
                       JSON_OBJECT(
                           'product_id', oi.product_id,
                           'sku', oi.product_sku,
                           'name', oi.product_name,
                           'quantity', oi.quantity,
                           'unit_price', oi.unit_price,
                           'subtotal', oi.subtotal
                       )
                   ) as items
            FROM orders o
            LEFT JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.order_id = ? AND o.deleted_at IS NULL
            GROUP BY o.order_id
            """,
            (order_id,)
        )
        
        if order:
            # Cache for 5 minutes
            await self.cache.setex(
                f'order:{order_id}',
                300,
                order.json()
            )
        
        return order
    
    async def get_customer_orders(
        self, 
        customer_id: int, 
        limit: int = 20,
        offset: int = 0,
        status_filter: Optional[List[str]] = None
    ) -> List[Order]:
        """Get paginated customer orders with optional status filter"""
        cache_key = f'customer:{customer_id}:orders:{offset//limit}:{",".join(status_filter or [])}'
        
        # Try cache
        cached = await self.cache.get(cache_key)
        if cached:
            return [Order.parse_raw(o) for o in json.loads(cached)]
        
        # Build query
        where_clause = "customer_id = ? AND deleted_at IS NULL"
        params = [customer_id]
        
        if status_filter:
            placeholders = ','.join('?' * len(status_filter))
            where_clause += f" AND status IN ({placeholders})"
            params.extend(status_filter)
        
        orders = await self.db.execute(
            f"""
            SELECT order_id, order_number, status, total_amount, 
                   created_at, updated_at
            FROM orders
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            (*params, limit, offset)
        )
        
        # Cache for 2 minutes
        await self.cache.setex(cache_key, 120, json.dumps([o.dict() for o in orders]))
        
        return orders
    
    async def update_order_status(
        self, 
        order_id: int, 
        new_status: str,
        user: str
    ) -> bool:
        """Update status with validation and audit trail"""
        async with self.db.transaction():
            order = await self.db.execute(
                """
                SELECT order_id, status, version
                FROM orders
                WHERE order_id = ?
                FOR UPDATE
                """,
                (order_id,)
            )
            
            if not order:
                return False
            
            # Validate transition
            if not OrderStatusTransition.is_valid_transition(
                order.status, new_status
            ):
                raise InvalidStatusTransitionError(
                    f"Cannot transition from {order.status} to {new_status}"
                )
            
            # Update with optimistic lock
            timestamp_field = self._get_timestamp_field(new_status)
            updated = await self.db.execute(
                f"""
                UPDATE orders
                SET status = ?,
                    {timestamp_field} = NOW(),
                    version = version + 1
                WHERE order_id = ? AND version = ?
                """,
                (new_status, order_id, order.version)
            )
            
            if updated == 0:
                raise ConcurrencyError("Order was modified concurrently")
            
            # Record history
            await self._record_status_change(
                order_id, order.status, new_status, user
            )
            
            # Invalidate cache
            await self.cache.delete(f'order:{order_id}')
            
            return True
    
    def _get_timestamp_field(self, status: str) -> str:
        """Map status to timestamp field"""
        mapping = {
            'confirmed': 'payment_confirmed_at',
            'shipped': 'shipped_at',
            'delivered': 'delivered_at',
            'cancelled': 'cancelled_at'
        }
        return mapping.get(status, 'updated_at')
    
    async def _record_status_change(
        self, 
        order_id: int, 
        from_status: str, 
        to_status: str, 
        user: str
    ):
        """Record status change in audit trail"""
        await self.db.execute(
            """
            INSERT INTO order_status_history 
            (order_id, from_status, to_status, changed_by)
            VALUES (?, ?, ?, ?)
            """,
            (order_id, from_status, to_status, user)
        )
    
    async def _generate_order_number(self) -> str:
        """Generate unique order number (e.g., ORD-20240117-ABC123)"""
        # Use Redis INCR for distributed counter
        date_part = datetime.utcnow().strftime('%Y%m%d')
        counter = await self.cache.incr(f'order_counter:{date_part}')
        return f'ORD-{date_part}-{counter:06d}'


class BackgroundJobService:
    """Cleanup and maintenance jobs"""
    
    async def release_expired_reservations(self):
        """
        Run every minute to release expired reservations
        """
        expired = await self.db.execute(
            """
            SELECT reservation_id, product_id, quantity
            FROM inventory_reservations
            WHERE status = 'active' 
            AND expires_at < NOW()
            LIMIT 1000
            FOR UPDATE SKIP LOCKED
            """
        )
        
        for reservation in expired:
            async with self.db.transaction():
                # Mark as expired
                await self.db.execute(
                    """
                    UPDATE inventory_reservations
                    SET status = 'expired'
                    WHERE reservation_id = ?
                    """,
                    (reservation.reservation_id,)
                )
                
                # Release reserved stock
                await self.db.execute(
                    """
                    UPDATE products
                    SET reserved_quantity = GREATEST(0, reserved_quantity - ?)
                    WHERE product_id = ?
                    """,
                    (reservation.quantity, reservation.product_id)
                )
    
    async def cancel_abandoned_carts(self):
        """
        Cancel orders stuck in cart/pending_payment after timeout
        """
        await self.db.execute(
            """
            UPDATE orders
            SET status = 'cancelled',
                cancelled_at = NOW()
            WHERE status IN ('cart', 'pending_payment')
            AND created_at < DATE_SUB(NOW(), INTERVAL 2 HOUR)
            AND cancelled_at IS NULL
            """
        )
```

#### 3. Enhanced Caching Strategy

```python
# Redis cache keys with TTL
CACHE_CONFIG = {
    # Read-heavy, changes infrequently
    'order': {
        'key': 'order:{order_id}',
        'ttl': 300,  # 5 minutes
    },
    # Very read-heavy, acceptable staleness
    'customer_orders': {
        'key': 'customer:{customer_id}:orders:{page}:{status_filter}',
        'ttl': 120,  # 2 minutes
    },
    # Analytics data
    'order_stats': {
        'key': 'stats:orders:{date}:{metric}',
        'ttl': 3600,  # 1 hour
    },
    # Product stock (critical for flash sales)
    'product_stock': {
        'key': 'product:{product_id}:stock',
        'ttl': 60,  # 1 minute, frequent updates
    },
    # Distributed counter
    'order_counter': {
        'key': 'order_counter:{date}',
        'ttl': 86400,  # 24 hours
    }
}

# Cache invalidation patterns
INVALIDATION_RULES = {
    'order_created': [
        'customer:{customer_id}:orders:*',
        'stats:orders:*'
    ],
    'order_updated': [
        'order:{order_id}',
        'customer:{customer_id}:orders:*'
    ],
    'stock_changed': [
        'product:{product_id}:stock'
    ]
}
```

#### 4. Indexing Strategy Rationale

**Primary Indexes (Unchanged - Already Optimal):**
- `idx_customer_created (customer_id, created_at DESC)`: Customer order history
- `idx_status_created (status, created_at DESC)`: Admin filtering
- `idx_order_number (order_number)`: Order lookup

**New Indexes Added:**
- `idx_customer_status (customer_id, status, created_at DESC)`: Covering index for filtered customer queries
- `idx_status_updated (status, updated_at)`: Cleanup jobs targeting stale orders
- `idx_deleted_at (deleted_at)`: Soft delete queries
- `idx_status_expires (status, expires_at)` on reservations: Critical for cleanup job performance
- `idx_product_status (product_id, status)` on reservations: Stock availability checks

**Index Maintenance:**
- Use `ANALYZE TABLE` weekly to update statistics
- Monitor index usage with `sys.schema_unused_indexes`
- Consider partitioning orders table after 10M+ rows

#### 5. Scaling Strategy

**Horizontal Partitioning:**
```sql
-- Partition orders by creation date (improves query locality)
ALTER TABLE orders PARTITION BY RANGE (UNIX_TIMESTAMP(created_at)) (
    PARTITION p_2024_q1 VALUES LESS THAN (UNIX_TIMESTAMP('2024-04-01')),
    PARTITION p_2024_q2 VALUES LESS THAN (UNIX_TIMESTAMP('2024-07-01')),
    PARTITION p_2024_q3 VALUES LESS THAN (UNIX_TIMESTAMP('2024-10-01')),
    PARTITION p_2024_q4 VALUES LESS THAN (UNIX_TIMESTAMP('2025-01-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- Partition reservations by expiry (efficient cleanup)
ALTER TABLE inventory_reservations 
PARTITION BY RANGE (UNIX_TIMESTAMP(expires_at)) (
    PARTITION p_current VALUES LESS THAN (UNIX_TIMESTAMP('2024-02-01')),
    PARTITION p_next VALUES LESS THAN (UNIX_TIMESTAMP('2024-03-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);
-- Drop old partitions monthly
```

**Read/Write Separation:**
```
Primary (Write Master):
- All INSERT, UPDATE, DELETE operations
- Order creation, status updates
- Stock reservations

Read Replicas (2-3 instances):
- Customer order history queries
- Admin dashboard queries
- Product catalog browsing

Analytics Replica (Separate):
- Long-running reports
- Data exports
- Business intelligence queries
```

**Sharding Strategy (50M+ orders):**
```python
# Shard by customer_id hash (preserves query locality)
def get_shard_id(customer_id: int, num_shards: int = 16) -> int:
    return customer_id % num_shards

# Order lookup by order_number requires:
# 1. Maintain order_number -> shard_id mapping in Redis
# 2. Query specific shard directly
# 3. Fallback to broadcast query if mapping miss
```

#### 6. Flash Sale Handling

**Rate Limiting:**
```python
class FlashSaleRateLimiter:
    """Prevent thundering herd during flash sales"""
    
    async def check_rate_limit(self, customer_id: int, product_id: int) -> bool:
        """
        Sliding window rate limit:
        - Max 5 purchase attempts per minute per customer
        - Max 10 purchase attempts per product per second globally
        """
        customer_key = f'rate_limit:customer:{customer_id}'
        product_key = f'rate_limit:product:{product_id}'
        
        # Customer-level limit
        customer_count = await self.cache.incr(customer_key)
        if customer_count == 1:
            await self.cache.expire(customer_key, 60)
        if customer_count > 5:
            return False
        
        # Product-level limit (distributed counter)
        product_count = await self.cache.incr(product_key)
        if product_count == 1:
            await self.cache.expire(product_key, 1)
        if product_count > 10:
            return False
        
        return True
```

**Queue-Based Processing:**
```python
class OrderQueueService:
    """Queue orders during high traffic to prevent database overload"""
    
    async def enqueue_order(self, order_request: OrderCreate) -> str:
        """
        Add order to Redis queue and return ticket ID
        Process asynchronously with worker pool
        """
        ticket_id = f'ticket_{uuid.uuid4().hex}'
        
        await self.cache.lpush(
            'order_queue',
            json.dumps({
                'ticket_id': ticket_id,
                'customer_id': order_request.customer_id,
                'items': order_request.items,
                'timestamp': time.time()
            })
        )
        
        # Store ticket status
        await self.cache.setex(
            f'ticket:{ticket_id}',
            1800,  # 30 minutes
            json.dumps({'status': 'pending', 'position': await self._get_queue_position()})
        )
        
        return ticket_id
    
    async def process_order_queue(self):
        """
        Worker process: consume orders from queue with concurrency control
        """
        while True:
            # Process in batches to maximize throughput
            batch = await self.cache.rpop('order_queue', count=10)
            
            if not batch:
                await asyncio.sleep(0.1)
                continue
            
            # Process orders concurrently (limited by semaphore)
            async with asyncio.Semaphore(5):  # Max 5 concurrent orders
                tasks = [self._process_single_order(order) for order in batch]
                await asyncio.gather(*tasks, return_exceptions=True)
```

#### 7. Error Handling & Data Consistency

**Concurrency Control:**
```python
class OrderStatusTransition:
    """Valid state transitions with business rules"""
    VALID_TRANSITIONS = {
        'cart': ['pending_payment', 'cancelled'],
        'pending_payment': ['payment_failed', 'confirmed', 'cancelled'],
        'payment_failed': ['pending_payment', 'cancelled'],
        'confirmed': ['processing', 'cancelled'],
        'processing': ['shipped', 'cancelled'],
        'shipped': ['delivered', 'cancelled'],
        'delivered': ['refunded'],
        'cancelled': [],  # Terminal state
        'refunded': []    # Terminal state
    }
    
    @staticmethod
    def is_valid_transition(from_status: str, to_status: str) -> bool:
        return to_status in VALID_TRANSITIONS.get(from_status, [])
    
    @staticmethod
    def requires_inventory_release(from_status: str, to_status: str) -> bool:
        """Some transitions require releasing reserved inventory"""
        return from_status in ('cart', 'pending_payment') and to_status == 'cancelled'
```

**Idempotency:**
```python
class IdempotencyMiddleware:
    """Prevent duplicate order creation from retries"""
    
    async def handle_request(self, request_id: str, handler):
        """
        Check if request was already processed
        Cache result for 24 hours
        """
        cache_key = f'idempotency:{request_id}'
        cached_result = await self.cache.get(cache_key)
        
        if cached_result:
            return json.loads(cached_result)
        
        # Process request
        result = await handler()
        
        # Cache result
        await self.cache.setex(cache_key, 86400, json.dumps(result))
        
        return result
```

**Saga Pattern for Distributed Transactions:**
```python
class OrderCreationSaga:
    """
    Compensating transactions for order creation failures
    
    Steps:
    1. Reserve inventory
    2. Create order record
    3. Process payment
    4. Confirm order
    
    If any step fails, rollback previous steps
    """
    
    async def execute(self, order_request: OrderCreate) -> Order:
        compensations = []
        
        try:
            # Step 1: Reserve inventory
            reservations = await self._reserve_inventory(order_request.items)
            compensations.append(lambda: self._release_reservations(reservations))
            
            # Step 2: Create order
            order = await self._create_order(order_request, reservations)
            compensations.append(lambda: self._delete_order(order.order_id))
            
            # Step 3: Process payment
            payment = await self._process_payment(order)
            compensations.append(lambda: self._refund_payment(payment.payment_id))
            
            # Step 4: Confirm order
            await self._confirm_order(order.order_id)
            
            return order
            
        except Exception as e:
            # Execute compensations in reverse order
            for compensation in reversed(compensations):
                try:
                    await compensation()
                except Exception as comp_error:
                    logger.error(f"Compensation failed: {comp_error}")
            
            raise OrderCreationError(f"Order creation failed: {e}")
```

## What I Improved

1. **Inventory Reservation System**: Added dedicated `inventory_reservations` table with TTL-based expiry to handle flash sales and prevent overselling. This solves the high-concurrency bottleneck the architect asked about.

2. **Optimistic Locking**: Added `version` columns to `orders`, `products`, and `customers` tables to detect concurrent modifications and prevent lost updates.

3. **Two-Phase Inventory Management**: Products now have both `stock_quantity` and `reserved_quantity`, allowing immediate stock checks without locking while preventing overselling.

4. **Enhanced Order Lifecycle**: Added intermediate states (`cart`, `pending_payment`, `payment_failed`) to handle real-world payment flows and abandoned carts.

5. **Database Locking Strategy**: Implemented `SELECT FOR UPDATE` with `SKIP LOCKED` for high-concurrency scenarios (cleanup jobs, flash sales), preventing lock contention.

6. **Background Jobs**: Added cleanup services for expired reservations and abandoned carts to prevent resource leaks.

7. **Soft Delete Support**: Added `deleted_at` column to orders for audit compliance while maintaining referential integrity.

8. **Multi-Currency Support**: Added `currency_code` field to support international operations.

9. **Queue-Based Order Processing**: Implemented async queue system for handling traffic spikes during flash sales.

10. **Idempotency Guarantees**: Added request deduplication to prevent duplicate orders from client retries.

11. **Additional Strategic Indexes**: Added covering indexes for common filtered queries and maintenance job optimization.

12. **Row Compression**: Applied `ROW_FORMAT=COMPRESSED` to orders table for better storage efficiency on historical data.

## What I Kept

1. **Core Table Structure**: The base schema design with denormalized addresses is excellent for read performance - kept intact.

2. **Composite Indexes**: The original indexing strategy (customer_created, status_created) is optimal for read queries - kept all.

3. **Audit Trail Design**: The `order_status_history` table provides perfect compliance tracking - unchanged.

4. **Denormalization Approach**: Storing address snapshots and product details in orders prevents JOIN overhead - this is correct.

5. **InnoDB Engine**: Correct choice for ACID compliance and foreign key support.

6. **Data Types**: DECIMAL for currency, ENUM for statuses, BIGINT for IDs - all appropriate.

7. **Cascade Delete**: Order items cascade delete with orders - maintains consistency.

8. **Cache-Aside Pattern**: The caching strategy with TTL is sound - enhanced with additional patterns.

## Remaining Concerns

1. **Payment Integration**: Still not addressed - recommend separate `payments` table with external payment gateway reference for PCI compliance.

2. **Geographic Sharding**: For global operations, may need to shard by region rather than customer_id hash to minimize latency.

3. **Warehouse Management**: Multiple fulfillment centers would require `inventory_locations` table and location-aware stock allocation.

4. **Reservation Expiry Cleanup**: At massive scale (1M+ active reservations), cleanup job may become bottleneck - consider partitioning by expiry date.

5. **Database Connection Pooling**: High-concurrency scenarios require careful connection pool tuning (recommend 20-50 connections per replica).

6. **Index Maintenance Overhead**: With 7+ indexes on orders table, write performance may degrade - monitor and consider archive strategy.

## Convergence Status

**ITERATING** - Design significantly improved for concurrency, but needs architect's input on payment integration and warehouse management.

## PROMPT_FOR_ARCHITECT:

Please focus on:
1. **Payment integration design**: How should we structure the payments table and handle payment gateway webhooks while maintaining data consistency with orders?
2. **Multi-warehouse inventory**: If we need to support multiple fulfillment centers, how should we adapt the inventory reservation logic to allocate stock from the nearest warehouse?
3. **Archive strategy**: For orders older than 2 years, should we implement a separate archive database or use cold storage partitions?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

### E-Commerce Order System - Complete Production-Ready Schema

#### 1. Enhanced Core Schema with Payment & Warehouse Support

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
    latitude DECIMAL(10,8),  -- For distance calculations
    longitude DECIMAL(11,8),
    status ENUM('active', 'inactive', 'maintenance') NOT NULL DEFAULT 'active',
    priority INT NOT NULL DEFAULT 100,  -- Lower = higher priority
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status_priority (status, priority),
    INDEX idx_location (latitude, longitude)
) ENGINE=InnoDB;

CREATE TABLE products (
    product_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    sku VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    base_price DECIMAL(10,2) NOT NULL,  -- Renamed from 'price'
    weight_grams INT,  -- For shipping calculations
    status ENUM('active', 'inactive', 'discontinued') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    version INT NOT NULL DEFAULT 1,
    
    INDEX idx_sku (sku),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- Multi-warehouse inventory tracking
CREATE TABLE warehouse_inventory (
    inventory_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    product_id BIGINT NOT NULL,
    stock_quantity INT NOT NULL DEFAULT 0,
    reserved_quantity INT NOT NULL DEFAULT 0,
    safety_stock_level INT NOT NULL DEFAULT 0,  -- Reorder point
    last_restock_at TIMESTAMP NULL,
    version INT NOT NULL DEFAULT 1,  -- Optimistic locking per location
    
    UNIQUE KEY uk_warehouse_product (warehouse_id, product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    
    INDEX idx_product_warehouse (product_id, warehouse_id),
    INDEX idx_low_stock (warehouse_id, stock_quantity),
    
    CHECK (stock_quantity >= 0),
    CHECK (reserved_quantity >= 0),
    CHECK (reserved_quantity <= stock_quantity)
) ENGINE=InnoDB;

-- Inventory reservations with warehouse allocation
CREATE TABLE inventory_reservations (
    reservation_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    product_id BIGINT NOT NULL,
    order_id BIGINT NULL,
    customer_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    status ENUM('active', 'expired', 'completed', 'cancelled') NOT NULL DEFAULT 'active',
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    
    INDEX idx_status_expires (status, expires_at),
    INDEX idx_warehouse_product_status (warehouse_id, product_id, status),
    INDEX idx_order_id (order_id),
    INDEX idx_customer_created (customer_id, created_at)
) ENGINE=InnoDB;

-- ============================================
-- ORDERS & FULFILLMENT
-- ============================================

CREATE TABLE orders (
    order_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    customer_id BIGINT NOT NULL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    
    -- Status tracking
    status ENUM(
        'cart', 
        'pending_payment', 
        'payment_processing',
        'payment_failed', 
        'payment_confirmed',
        'confirmed', 
        'processing', 
        'shipped', 
        'delivered', 
        'cancelled', 
        'refunded'
    ) NOT NULL DEFAULT 'cart',
    
    -- Financial details
    subtotal_amount DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    
    -- Fulfillment warehouse
    fulfillment_warehouse_id INT NULL,
    
    -- Shipping information (immutable snapshot)
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country CHAR(2),
    
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
    
    -- Critical indexes for common queries
    INDEX idx_customer_created (customer_id, created_at DESC),
    INDEX idx_status_created (status, created_at DESC),
    INDEX idx_order_number (order_number),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_customer_status (customer_id, status, created_at DESC),
    INDEX idx_status_updated (status, updated_at),
    INDEX idx_warehouse_status (fulfillment_warehouse_id, status, created_at),
    INDEX idx_deleted_at (deleted_at)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED;

CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    warehouse_id INT NOT NULL,  -- Where this item is fulfilled from
    
    -- Immutable product snapshot
    product_sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    subtotal DECIMAL(10,2) NOT NULL,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_product_id (product_id),
    INDEX idx_warehouse_created (warehouse_id, created_at),
    INDEX idx_product_created (product_id, created_at)
) ENGINE=InnoDB;

-- ============================================
-- PAYMENT SYSTEM
-- ============================================

CREATE TABLE payments (
    payment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    
    -- Payment gateway details
    payment_gateway ENUM('stripe', 'paypal', 'square', 'adyen') NOT NULL,
    gateway_transaction_id VARCHAR(255),  -- External reference
    gateway_customer_id VARCHAR(255),  -- For recurring payments
    
    -- Payment method
    payment_method ENUM('credit_card', 'debit_card', 'paypal', 'bank_transfer', 'crypto') NOT NULL,
    card_last_four CHAR(4),
    card_brand VARCHAR(20),
    
    -- Financial details
    amount DECIMAL(12,2) NOT NULL,
    currency_code CHAR(3) NOT NULL,
    
    -- Status tracking
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
    
    -- Failure information
    failure_code VARCHAR(50),
    failure_message TEXT,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    authorized_at TIMESTAMP NULL,
    captured_at TIMESTAMP NULL,
    failed_at TIMESTAMP NULL,
    refunded_at TIMESTAMP NULL,
    
    -- Idempotency
    idempotency_key VARCHAR(255) UNIQUE,
    
    -- Metadata (JSON for gateway-specific data)
    metadata JSON,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_gateway_transaction (payment_gateway, gateway_transaction_id),
    INDEX idx_status_created (status, created_at),
    INDEX idx_idempotency_key (idempotency_key),
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB;

CREATE TABLE payment_events (
    event_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_id BIGINT NOT NULL,
    
    -- Event details
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
        'webhook_received'
    ) NOT NULL,
    
    -- Gateway webhook data
    gateway_event_id VARCHAR(255),
    gateway_event_type VARCHAR(100),
    
    -- Event payload (full webhook or API response)
    event_payload JSON,
    
    -- Processing status
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMP NULL,
    processing_error TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE,
    
    INDEX idx_payment_created (payment_id, created_at DESC),
    INDEX idx_gateway_event (gateway_event_id),
    INDEX idx_processed_created (processed, created_at),
    INDEX idx_event_type (event_type, created_at)
) ENGINE=InnoDB;

-- Refunds tracking
CREATE TABLE refunds (
    refund_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_id BIGINT NOT NULL,
    order_id BIGINT NOT NULL,
    
    -- Refund details
    refund_amount DECIMAL(12,2) NOT NULL,
    refund_reason ENUM('customer_request', 'fraud', 'duplicate', 'product_issue', 'other') NOT NULL,
    refund_notes TEXT,
    
    -- Gateway details
    gateway_refund_id VARCHAR(255),
    
    status ENUM('pending', 'processing', 'succeeded', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    created_by VARCHAR(100),  -- User or system that initiated refund
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    
    INDEX idx_payment_id (payment_id),
    INDEX idx_order_id (order_id),
    INDEX idx_status_created (status, created_at),
    INDEX idx_created_at (created_at DESC)
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
-- ARCHIVAL STRATEGY
-- ============================================

-- Same schema as orders but for completed/old orders
CREATE TABLE orders_archive (
    -- Identical structure to orders table
    -- Populated by monthly archive job
    -- Partitioned by year for efficient cold storage
    -- Primary indexes only (customer_id, order_number, created_at)
    LIKE orders
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED;

-- Archive metadata tracking
CREATE TABLE archive_batches (
    batch_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    archive_date DATE NOT NULL,
    orders_archived INT NOT NULL,
    oldest_order_date TIMESTAMP NOT NULL,
    newest_order_date TIMESTAMP NOT NULL,
    status ENUM('in_progress', 'completed', 'failed') NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    INDEX idx_archive_date (archive_date),
    INDEX idx_status (status)
) ENGINE=InnoDB;
```

#### 2. Multi-Warehouse Inventory Service

```python
from typing import List, Optional, Tuple
from dataclasses import dataclass
from geopy.distance import geodesic

@dataclass
class WarehouseAllocation:
    warehouse_id: int
    warehouse_code: str
    quantity: int
    distance_km: float

class MultiWarehouseInventoryService:
    """
    Intelligent warehouse allocation based on:
    1. Geographic proximity to shipping address
    2. Stock availability
    3. Warehouse priority/capacity
    """
    
    async def reserve_stock_multi_warehouse(
        self,
        product_id: int,
        quantity: int,
        customer_id: int,
        shipping_address: Address,
        order_id: Optional[int] = None,
        ttl_seconds: int = 900
    ) -> List[WarehouseAllocation]:
        """
        Allocate stock from optimal warehouses.
        
        Strategy:
        1. Find all warehouses with available stock
        2. Calculate distance from shipping address
        3. Allocate from nearest warehouse first
        4. If insufficient, allocate from next nearest (split-shipment)
        5. Lock inventory with reservations
        
        Returns list of warehouse allocations or raises InsufficientStockError
        """
        # Get customer coordinates (geocode shipping address)
        customer_coords = await self._geocode_address(shipping_address)
        
        async with self.db.transaction():
            # Find warehouses with available stock, ordered by proximity
            available_warehouses = await self.db.execute(
                """
                SELECT 
                    w.warehouse_id,
                    w.warehouse_code,
                    w.latitude,
                    w.longitude,
                    w.priority,
                    wi.stock_quantity,
                    wi.reserved_quantity,
                    wi.version,
                    (wi.stock_quantity - wi.reserved_quantity) as available_quantity
                FROM warehouses w
                JOIN warehouse_inventory wi ON w.warehouse_id = wi.warehouse_id
                WHERE wi.product_id = ?
                    AND w.status = 'active'
                    AND (wi.stock_quantity - wi.reserved_quantity) > 0
                FOR UPDATE  -- Lock warehouse inventory rows
                """,
                (product_id,)
            )
            
            if not available_warehouses:
                raise InsufficientStockError(f"Product {product_id} out of stock")
            
            # Calculate distances and sort by proximity, then priority
            warehouses_with_distance = [
                {
                    **wh,
                    'distance_km': self._calculate_distance(
                        customer_coords,
                        (wh.latitude, wh.longitude)
                    )
                }
                for wh in available_warehouses
            ]
            
            # Sort by distance first, then priority
            warehouses_with_distance.sort(
                key=lambda x: (x['distance_km'], x['priority'])
            )
            
            # Allocate stock greedily from nearest warehouses
            allocations = []
            remaining_quantity = quantity
            
            for warehouse in warehouses_with_distance:
                if remaining_quantity <= 0:
                    break
                
                allocate_qty = min(
                    remaining_quantity,
                    warehouse['available_quantity']
                )
                
                # Create reservation
                expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
                reservation_id = await self.db.execute(
                    """
                    INSERT INTO inventory_reservations
                    (warehouse_id, product_id, order_id, customer_id, 
                     quantity, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (warehouse['warehouse_id'], product_id, order_id,
                     customer_id, allocate_qty, expires_at)
                )
                
                # Update reserved quantity with optimistic lock
                updated = await self.db.execute(
                    """
                    UPDATE warehouse_inventory
                    SET reserved_quantity = reserved_quantity + ?,
                        version = version + 1
                    WHERE warehouse_id = ? 
                        AND product_id = ?
                        AND version = ?
                    """,
                    (allocate_qty, warehouse['warehouse_id'],
                     product_id, warehouse['version'])
                )
                
                if updated == 0:
                    raise ConcurrencyError(
                        f"Warehouse {warehouse['warehouse_id']} inventory "
                        "was modified concurrently"
                    )
                
                allocations.append(WarehouseAllocation(
                    warehouse_id=warehouse['warehouse_id'],
                    warehouse_code=warehouse['warehouse_code'],
                    quantity=allocate_qty,
                    distance_km=warehouse['distance_km']
                ))
                
                remaining_quantity -= allocate_qty
            
            # Check if we fulfilled the entire order
            if remaining_quantity > 0:
                raise InsufficientStockError(
                    f"Only {quantity - remaining_quantity}/{quantity} "
                    f"units available for product {product_id}"
                )
            
            return allocations
    
    async def confirm_multi_warehouse_reservation(
        self,
        order_id: int
    ) -> bool:
        """
        Confirm all reservations for an order and deduct stock.
        Called after payment confirmation.
        """
        async with self.db.transaction():
            # Get all active reservations for this order
            reservations = await self.db.execute(
                """
                SELECT reservation_id, warehouse_id, product_id, quantity
                FROM inventory_reservations
                WHERE order_id = ? AND status = 'active'
                FOR UPDATE
                """,
                (order_id,)
            )
            
            for reservation in reservations:
                # Mark reservation completed
                await self.db.execute(
                    """
                    UPDATE inventory_reservations
                    SET status = 'completed',
                        completed_at = NOW()
                    WHERE reservation_id = ?
                    """,
                    (reservation.reservation_id,)
                )
                
                # Deduct from actual stock and reserved quantity
                await self.db.execute(
                    """
                    UPDATE warehouse_inventory
                    SET stock_quantity = stock_quantity - ?,
                        reserved_quantity = GREATEST(0, reserved_quantity - ?),
                        version = version + 1
                    WHERE warehouse_id = ? AND product_id = ?
                    """,
                    (reservation.quantity, reservation.quantity,
                     reservation.warehouse_id, reservation.product_id)
                )
            
            return True
    
    async def get_total_available_stock(
        self,
        product_id: int
    ) -> int:
        """Get total available stock across all warehouses"""
        result = await self.db.execute(
            """
            SELECT COALESCE(SUM(stock_quantity - reserved_quantity), 0) as total
            FROM warehouse_inventory wi
            JOIN warehouses w ON wi.warehouse_id = w.warehouse_id
            WHERE wi.product_id = ? AND w.status = 'active'
            """,
            (product_id,)
        )
        return result.total
    
    async def _geocode_address(self, address: Address) -> Tuple[float, float]:
        """
        Convert address to coordinates.
        Cache results to avoid API calls.
        """
        cache_key = f"geocode:{address.postal_code}:{address.country}"
        cached = await self.cache.get(cache_key)
        
        if cached:
            return tuple(json.loads(cached))
        
        # Use geocoding service (Google Maps, Mapbox, etc.)
        coords = await self.geocoding_service.geocode(
            f"{address.city}, {address.state} {address.postal_code}, {address.country}"
        )
        
        # Cache for 30 days
        await self.cache.setex(cache_key, 2592000, json.dumps(coords))
        
        return coords
    
    def _calculate_distance(
        self,
        coord1: Tuple[float, float],
        coord2: Tuple[float, float]
    ) -> float:
        """Calculate distance in kilometers using Haversine formula"""
        return geodesic(coord1, coord2).kilometers
```

#### 3. Payment Integration Service

```python
from enum import Enum
from typing import Optional
import hashlib
import hmac

class PaymentGateway(Enum):
    STRIPE = 'stripe'
    PAYPAL = 'paypal'
    SQUARE = 'square'
    ADYEN = 'adyen'

class PaymentService:
    """
    Handles payment processing with webhook event handling.
    
    Design principles:
    1. Idempotent payment operations
    2. Async webhook processing with event sourcing
    3. Automatic retry with exponential backoff
    4. State machine for payment lifecycle
    """
    
    async def initiate_payment(
        self,
        order_id: int,
        payment_method: str,
        idempotency_key: Optional[str] = None
    ) -> Payment:
        """
        Start payment process.
        
        Flow:
        1. Check for existing payment with idempotency key
        2. Create payment record in 'pending' status
        3. Call payment gateway API
        4. Update payment with gateway transaction ID
        """
        if not idempotency_key:
            idempotency_key = f"order_{order_id}_{int(time.time())}"
        
        # Check for duplicate request
        existing = await self.db.execute(
            """
            SELECT payment_id, status
            FROM payments
            WHERE idempotency_key = ?
            """,
            (idempotency_key,)
        )
        
        if existing:
            return await self.get_payment(existing.payment_id)
        
        async with self.db.transaction():
            # Get order details
            order = await self.db.execute(
                """
                SELECT order_id, customer_id, total_amount, currency_code
                FROM orders
                WHERE order_id = ? AND status = 'pending_payment'
                FOR UPDATE
                """,
                (order_id,)
            )
            
            if not order:
                raise InvalidOrderStateError(
                    f"Order {order_id} not in pending_payment state"
                )
            
            # Create payment record
            payment_id = await self.db.execute(
                """
                INSERT INTO payments (
                    order_id,
                    payment_gateway,
                    payment_method,
                    amount,
                    currency_code,
                    status,
                    idempotency_key
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (order_id, PaymentGateway.STRIPE.value, payment_method,
                 order.total_amount, order.currency_code, idempotency_key)
            )
            
            # Log event
            await self._log_payment_event(
                payment_id,
                'payment_initiated',
                {'order_id': order_id}
            )
            
            # Update order status
            await self.db.execute(
                """
                UPDATE orders
                SET status = 'payment_processing'
                WHERE order_id = ?
                """,
                (order_id,)
            )
        
        # Call payment gateway (outside transaction)
        try:
            gateway_response = await self._call_payment_gateway(
                payment_id=payment_id,
                amount=order.total_amount,
                currency=order.currency_code,
                payment_method=payment_method
            )
            
            # Update with gateway details
            await self.db.execute(
                """
                UPDATE payments
                SET gateway_transaction_id = ?,
                    status = 'processing',
                    metadata = ?
                WHERE payment_id = ?
                """,
                (gateway_response.transaction_id,
                 json.dumps(gateway_response.metadata),
                 payment_id)
            )
            
            await self._log_payment_event(
                payment_id,
                'authorization_requested',
                gateway_response.metadata
            )
            
        except PaymentGatewayError as e:
            await self._handle_payment_failure(
                payment_id,
                e.code,
                str(e)
            )
            raise
        
        return await self.get_payment(payment_id)
    
    async def handle_webhook(
        self,
        gateway: PaymentGateway,
        event_id: str,
        event_type: str,
        payload: dict,
        signature: str
    ) -> bool:
        """
        Process payment gateway webhook.
        
        Design:
        1. Verify webhook signature (prevent fraud)
        2. Check for duplicate event (idempotency)
        3. Store event in payment_events table
        4. Process event asynchronously
        5. Return 200 OK immediately (prevent retries)
        """
        # Verify signature
        if not self._verify_webhook_signature(gateway, payload, signature):
            raise WebhookVerificationError("Invalid webhook signature")
        
        # Check for duplicate event
        existing = await self.db.execute(
            """
            SELECT event_id, processed
            FROM payment_events
            WHERE gateway_event_id = ?
            """,
            (event_id,)
        )
        
        if existing:
            return existing.processed
        
        # Find associated payment
        gateway_txn_id = payload.get('transaction_id') or payload.get('id')
        payment = await self.db.execute(
            """
            SELECT payment_id, order_id, status
            FROM payments
            WHERE gateway_transaction_id = ?
            """,
            (gateway_txn_id,)
        )
        
        if not payment:
            # Store orphaned event for manual review
            await self._store_orphaned_event(gateway, event_id, event_type, payload)
            return False
        
        # Store event
        event_db_id = await self.db.execute(
            """
            INSERT INTO payment_events (
                payment_id,
                event_type,
                gateway_event_id,
                gateway_event_type,
                event_payload,
                processed
            )
            VALUES (?, ?, ?, ?, ?, FALSE)
            """,
            (payment.payment_id, self._map_event_type(event_type),
             event_id, event_type, json.dumps(payload))
        )
        
        # Process event asynchronously (queue for worker)
        await self.event_queue.enqueue({
            'event_id': event_db_id,
            'payment_id': payment.payment_id,
            'order_id': payment.order_id,
            'event_type': event_type,
            'payload': payload
        })
        
        return True
    
    async def process_payment_event(self, event_id: int):
        """
        Process payment event from queue (worker process).
        
        Updates payment status and order status based on event type.
        Idempotent - safe to retry.
        """
        async with self.db.transaction():
            # Lock event row
            event = await self.db.execute(
                """
                SELECT 
                    pe.payment_id,
                    pe.event_type,
                    pe.event_payload,
                    pe.processed,
                    p.order_id,
                    p.status as payment_status
                FROM payment_events pe
                JOIN payments p ON pe.payment_id = p.payment_id
                WHERE pe.event_id = ?
                FOR UPDATE
                """,
                (event_id,)
            )
            
            if not event or event.processed:
                return  # Already processed
            
            try:
                # Process based on event type
                if event.event_type == 'authorization_succeeded':
                    await self._handle_authorization_success(event)
                
                elif event.event_type == 'capture_succeeded':
                    await self._handle_capture_success(event)
                
                elif event.event_type == 'authorization_failed':
                    await self._handle_authorization_failure(event)
                
                elif event.event_type == 'refund_succeeded':
                    await self._handle_refund_success(event)
                
                # Mark event as processed
                await self.db.execute(
                    """
                    UPDATE payment_events
                    SET processed = TRUE,
                        processed_at = NOW()
                    WHERE event_id = ?
                    """,
                    (event_id,)
                )
                
            except Exception as e:
                # Log error but don't mark as processed (will retry)
                await self.db.execute(
                    """
                    UPDATE payment_events
                    SET processing_error = ?
                    WHERE event_id = ?
                    """,
                    (str(e), event_id)
                )
                raise
    
    async def _handle_authorization_success(self, event):
        """Payment authorized - confirm order and reserve inventory"""
        async with self.db.transaction():
            # Update payment status
            await self.db.execute(
                """
                UPDATE payments
                SET status = 'authorized',
                    authorized_at = NOW()
                WHERE payment_id = ?
                """,
                (event.payment_id,)
            )
            
            # Update order status
            await self.db.execute(
                """
                UPDATE orders
                SET status = 'payment_confirmed',
                    payment_confirmed_at = NOW()
                WHERE order_id = ?
                """,
                (event.order_id,)
            )
            
            # Confirm inventory reservations (deduct stock)
            await self.inventory_service.confirm_multi_warehouse_reservation(
                event.order_id
            )
            
            # Transition to confirmed
            await self.order_service.update_order_status(
                event.order_id,
                'confirmed',
                'payment_service'
            )
    
    async def _handle_capture_success(self, event):
        """Payment captured - funds secured"""
        await self.db.execute(
            """
            UPDATE payments
            SET status = 'captured',
                captured_at = NOW()
            WHERE payment_id = ?
            """,
            (event.payment_id,)
        )
    
    async def _handle_authorization_failure(self, event):
        """Payment failed - release inventory and update order"""
        payload = json.loads(event.event_payload)
        
        async with self.db.transaction():
            # Update payment status
            await self.db.execute(
                """
                UPDATE payments
                SET status = 'failed',
                    failed_at = NOW(),
                    failure_code = ?,
                    failure_message = ?
                WHERE payment_id = ?
                """,
                (payload.get('error_code'),
                 payload.get('error_message'),
                 event.payment_id)
            )
            
            # Update order status
            await self.db.execute(
                """
                UPDATE orders
                SET status = 'payment_failed'
                WHERE order_id = ?
                """,
                (event.order_id,)
            )
            
            # Release inventory reservations
            await self.inventory_service.release_order_reservations(
                event.order_id
            )
    
    def _verify_webhook_signature(
        self,
        gateway: PaymentGateway,
        payload: dict,
        signature: str
    ) -> bool:
        """Verify webhook came from payment gateway (prevent fraud)"""
        if gateway == PaymentGateway.STRIPE:
            # Stripe uses HMAC SHA256
            secret = self.config.stripe_webhook_secret
            computed = hmac.new(
                secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(computed, signature)
        
        # Implement for other gateways
        return True
    
    async def _log_payment_event(
        self,
        payment_id: int,
        event_type: str,
        payload: dict
    ):
        """Log internal payment event"""
        await self.db.execute(
            """
            INSERT INTO payment_events (
                payment_id,
                event_type,
                event_payload,
                processed
            )
            VALUES (?, ?, ?, TRUE)
            """,
            (payment_id, event_type, json.dumps(payload))
        )
```

#### 4. Archive Strategy Implementation

```python
class OrderArchiveService:
    """
    Archive old orders to separate table/storage.
    
    Strategy:
    - Archive orders older than 2 years and in terminal states
    - Run monthly as background job
    - Use partitioned archive table for efficient queries
    - Keep minimal indexes on archive table
    - Optionally export to cold storage (S3/BigQuery)
    """
    
    async def archive_old_orders(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000
    ) -> int:
        """
        Archive orders older than cutoff date.
        
        Process:
        1. Identify eligible orders (old + terminal state)
        2. Copy to orders_archive in batches
        3. Copy related records (items, history, payments)
        4. Soft-delete from main orders table
        5. Track in archive_batches table
        """
        terminal_states = ['delivered', 'cancelled', 'refunded']
        total_archived = 0
        
        # Create archive batch record
        batch_id = await self.db.execute(
            """
            INSERT INTO archive_batches (
                archive_date,
                orders_archived,
                oldest_order_date,
                newest_order_date,
                status
            )
            VALUES (CURDATE(), 0, ?, ?, 'in_progress')
            """,
            (cutoff_date, cutoff_date)
        )
        
        try:
            while True:
                async with self.db.transaction():
                    # Find batch of orders to archive
                    orders = await self.db.execute(
                        """
                        SELECT order_id
                        FROM orders
                        WHERE created_at < ?
                            AND status IN (?, ?, ?)
                            AND deleted_at IS NULL
                        LIMIT ?
                        FOR UPDATE SKIP LOCKED
                        """,
                        (cutoff_date, *terminal_states, batch_size)
                    )
                    
                    if not orders:
                        break  # No more orders to archive
                    
                    order_ids = [o.order_id for o in orders]
                    
                    # Copy orders to archive table
                    await self.db.execute(
                        """
                        INSERT INTO orders_archive
                        SELECT * FROM orders
                        WHERE order_id IN ({})
                        """.format(','.join('?' * len(order_ids))),
                        order_ids
                    )
                    
                    # Copy order items
                    await self.db.execute(
                        """
                        INSERT INTO order_items_archive
                        SELECT * FROM order_items
                        WHERE order_id IN ({})
                        """.format(','.join('?' * len(order_ids))),
                        order_ids
                    )
                    
                    # Copy status history
                    await self.db.execute(
                        """
                        INSERT INTO order_status_history_archive
                        SELECT * FROM order_status_history
                        WHERE order_id IN ({})
                        """.format(','.join('?' * len(order_ids))),
                        order_ids
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
                    
                    # Update batch progress
                    await self.db.execute(
                        """
                        UPDATE archive_batches
                        SET orders_archived = ?
                        WHERE batch_id = ?
                        """,
                        (total_archived, batch_id)
                    )
                
                # Small delay between batches to avoid overload
                await asyncio.sleep(0.5)
            
            # Mark batch complete
            await self.db.execute(
                """
                UPDATE archive_batches
                SET status = 'completed',
                    completed_at = NOW()
                WHERE batch_id = ?
                """,
                (batch_id,)
            )
            
            return total_archived
            
        except Exception as e:
            # Mark batch failed
            await self.db.execute(
                """
                UPDATE archive_batches
                SET status = 'failed'
                WHERE batch_id = ?
                """,
                (batch_id,)
            )
            raise
    
    async def query_archived_order(
        self,
        order_id: int
    ) -> Optional[Order]:
        """
        Query order from archive if not in main table.
        Transparent to API consumers.
        """
        # Try main table first
        order = await self.db.execute(
            """
            SELECT * FROM orders
            WHERE order_id = ? AND deleted_at IS NULL
            """,
            (order_id,)
        )
        
        if order:
            return order
        
        # Check archive
        order = await self.db.execute(
            """
            SELECT * FROM orders_archive
            WHERE order_id = ?
            """,
            (order_id,)
        )
        
        return order
    
    async def export_to_cold_storage(
        self,
        archive_date: date
    ):
        """
        Export archived orders to S3/BigQuery for long-term storage.
        Run quarterly for data older than 5 years.
        """
        # Query archived orders
        orders = await self.db.execute(
            """
            SELECT * FROM orders_archive
            WHERE created_at < DATE_SUB(?, INTERVAL 5 YEAR)
            """,
            (archive_date,)
        )
        
        # Export to S3 as compressed Parquet
        filename = f"orders_archive_{archive_date.isoformat()}.parquet"
        s3_key = f"archives/{archive_date.year}/{filename}"
        
        await self.export_service.export_to_parquet(
            orders,
            f"s3://{self.config.archive_bucket}/{s3_key}"
        )
        
        # Optionally delete from database after successful export
        # Keep metadata in archive_batches for reference
```

## Rationale

**1. Multi-Warehouse Design:**
- Separate `warehouses` and `warehouse_inventory` tables normalize warehouse data and enable per-location stock tracking
- Geographic coordinates on warehouses enable distance-based allocation
- Allocation algorithm prioritizes proximity then warehouse priority, minimizing shipping costs and delivery time
- Split-shipment support allows fulfilling orders from multiple locations when single warehouse lacks stock

**2. Payment Integration:**
- Separate `payments` table decouples payment lifecycle from order lifecycle (critical for refunds, disputes, retries)
- `payment_events` table implements event sourcing pattern - full audit trail of all payment state changes
- Webhook handling is idempotent via `gateway_event_id` uniqueness check
- Async event processing prevents webhook timeouts while maintaining consistency
- Signature verification prevents fraudulent webhook injection

**3. Archive Strategy:**
- Soft-delete approach (deleted_at) keeps data in main table initially for safety
- Monthly archive job moves old terminal-state orders to separate table
- Archive table has identical schema but minimal indexes (only for lookups)
- Transparent query layer checks both tables automatically
- Quarterly cold storage export to Parquet on S3 for data older than 5 years reduces database costs while maintaining compliance

**4. Inventory Reservation Enhancements:**
- Reservations now track `warehouse_id` for split-shipment support
- Completion timestamp added for analytics on reservation-to-sale conversion

**5. Payment-Order State Synchronization:**
- New order states: `payment_processing`, `payment_confirmed` separate authorization from capture
- Order status transitions triggered by payment webhook events ensure consistency
- Failed payments automatically release inventory reservations

## What I Changed

1. **Removed Single-Point Stock Tracking**: Eliminated single `stock_quantity` from products table, moved to per-warehouse tracking in `warehouse_inventory`

2. **Added Warehouse Infrastructure**: New `warehouses` table with geographic data and `warehouse_inventory` for distributed stock management

3. **Comprehensive Payment System**: Added three tables (`payments`, `payment_events`, `refunds`) to handle complete payment lifecycle with webhook event sourcing

4. **Enhanced Order States**: Added `payment_processing` and `payment_confirmed` states to accurately reflect payment authorization vs capture

5. **Archive Tables**: Added `orders_archive` and `archive_batches` tables for explicit archive management instead of relying solely on partitioning

6. **Order Item Warehouse Assignment**: Added `warehouse_id` to `order_items` to track fulfillment source per item

7. **Idempotency Keys**: Added `idempotency_key` to payments table for duplicate request prevention

8. **Payment Metadata**: Added JSON `metadata` field for gateway-specific data without schema changes

9. **Warehouse Distance Calculation**: Implemented geographic allocation algorithm using Haversine distance formula

10. **Event-Driven Payment Processing**: Async webhook handling with queue-based processing for reliability

## What I Kept

1. **Core Order Schema**: Original structure with denormalized addresses and timestamps is excellent

2. **Optimistic Locking**: Version columns on critical tables prevent lost updates

3. **Inventory Reservation Pattern**: Two-phase reservation system (reserve → confirm) remains unchanged

4. **Audit Trail**: `order_status_history` table for compliance tracking

5. **Index Strategy**: All original indexes plus targeted additions for warehouse queries

6. **Soft Delete Pattern**: `deleted_at` approach for orders

7. **Cache-Aside Strategy**: Redis caching with TTL-based invalidation

8. **Background Cleanup Jobs**: Expired reservation cleanup and abandoned cart cancellation

9. **Transaction Boundaries**: Proper use of database transactions for consistency

10. **Row Compression**: Compressed row format for orders table

## Open Questions

1. **Partial Refunds**: Should we track partial refunds at line-item level (order_item_id in refunds table) or keep order-level only?

2. **International Tax**: Do we need separate `tax_items` table for complex multi-jurisdiction tax calculations (VAT, GST, local taxes)?

3. **Warehouse Transfer**: Should we add `inventory_transfers` table to track stock movement between warehouses?

4. **Payment Authorization Hold Time**: How long should we hold authorization before auto-capture? Different gateways have different limits (7-30 days).

5. **Archive Deletion**: After exporting to cold storage, should we delete from `orders_archive` or keep indefinitely for fast queries?

6. **Geocoding Cache TTL**: 30 days for address geocoding - is this sufficient or should it be permanent?

## Convergence Status

**ITERATING** - First comprehensive design addressing all three requirements (payments, warehouses, archival), but needs validation on partial refund granularity and warehouse transfer tracking.

## PROMPT_FOR_CRITIC:

Please focus on:

1. **Payment Event Processing Reliability**: Is the async webhook processing design resilient enough? Should we add dead-letter queue for repeatedly failing events or automatic retry with exponential backoff?

2. **Warehouse Allocation Edge Cases**: What happens when customer changes shipping address after warehouse allocation? Should we reallocate or honor original assignment?

3. **Archive Query Performance**: Will the transparent query layer (check main table then archive) cause latency issues? Should we maintain order_id → table_location mapping in Redis for O(1) lookup?

4. **Split-Shipment Cost Analysis**: Should we add optimization to prefer single-warehouse fulfillment even if slightly farther, to reduce shipping costs from multiple origins?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

### E-Commerce Order System - Production-Hardened Schema with Enhanced Resilience

#### 1. Core Schema with Enhanced Payment & Warehouse Infrastructure

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
    max_daily_orders INT,  -- Capacity planning
    shipping_cost_base DECIMAL(8,2),  -- Base shipping cost from this warehouse
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status_priority (status, priority),
    INDEX idx_location (latitude, longitude)
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
    reallocation_reason VARCHAR(255),  -- Track why reallocation happened
    
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id),
    
    INDEX idx_status_expires (status, expires_at),
    INDEX idx_warehouse_product_status (warehouse_id, product_id, status),
    INDEX idx_order_id (order_id),
    INDEX idx_customer_created (customer_id, created_at)
) ENGINE=InnoDB;

-- NEW: Track warehouse-to-warehouse inventory transfers
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
        'confirmed', 
        'processing',
        'partially_shipped',  -- NEW: Support split shipments
        'shipped', 
        'delivered', 
        'cancelled', 
        'refunded',
        'partially_refunded'  -- NEW: Track partial refunds
    ) NOT NULL DEFAULT 'cart',
    
    -- Financial details
    subtotal_amount DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    refunded_amount DECIMAL(12,2) NOT NULL DEFAULT 0,  -- NEW: Track refunded amount
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    
    -- Primary fulfillment warehouse (most items)
    fulfillment_warehouse_id INT NULL,
    is_split_shipment BOOLEAN NOT NULL DEFAULT FALSE,  -- NEW: Flag for queries
    
    -- Shipping information (immutable snapshot)
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country CHAR(2),
    shipping_latitude DECIMAL(10,8),  -- NEW: Cached geocoded coords
    shipping_longitude DECIMAL(11,8),
    
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
    INDEX idx_split_shipment (is_split_shipment, status)  -- NEW: Query split orders
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
    refunded_quantity INT NOT NULL DEFAULT 0,  -- NEW: Track partial refunds
    refunded_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    
    -- Shipment tracking
    shipment_id BIGINT NULL,  -- NEW: Link to shipments table
    
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

-- NEW: Track individual shipments for split-shipment orders
CREATE TABLE shipments (
    shipment_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    warehouse_id INT NOT NULL,
    
    shipment_number VARCHAR(50) UNIQUE NOT NULL,
    carrier VARCHAR(100),
    tracking_number VARCHAR(255),
    
    status ENUM('pending', 'picked', 'packed', 'shipped', 'in_transit', 'delivered', 'failed') 
        NOT NULL DEFAULT 'pending',
    
    shipping_cost DECIMAL(10,2),
    estimated_delivery_date DATE,
    actual_delivery_date DATE,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    shipped_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_order_id (order_id),
    INDEX idx_warehouse_status (warehouse_id, status),
    INDEX idx_tracking_number (tracking_number),
    INDEX idx_status_created (status, created_at)
) ENGINE=InnoDB;

-- ============================================
-- PAYMENT SYSTEM WITH ENHANCED RELIABILITY
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
    retry_count INT NOT NULL DEFAULT 0,  -- NEW: Track retry attempts
    
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
    INDEX idx_retry_count (retry_count, status)  -- NEW: Find stuck payments
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
        'retry_scheduled',  -- NEW
        'moved_to_dlq'      -- NEW: Dead letter queue
    ) NOT NULL,
    
    gateway_event_id VARCHAR(255),
    gateway_event_type VARCHAR(100),
    
    event_payload JSON,
    
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    processed_at TIMESTAMP NULL,
    processing_error TEXT,
    retry_count INT NOT NULL DEFAULT 0,  -- NEW: Track event retry attempts
    next_retry_at TIMESTAMP NULL,        -- NEW: Exponential backoff
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id) ON DELETE CASCADE,
    
    UNIQUE KEY uk_gateway_event (gateway_event_id),  -- Prevent duplicate webhooks
    INDEX idx_payment_created (payment_id, created_at DESC),
    INDEX idx_processed_created (processed, created_at),
    INDEX idx_event_type (event_type, created_at),
    INDEX idx_retry_schedule (processed, next_retry_at),  -- NEW: Retry queue
    INDEX idx_retry_count (retry_count, processed)        -- NEW: Find problematic events
) ENGINE=InnoDB;

-- NEW: Dead letter queue for failed payment events
CREATE TABLE payment_events_dlq (
    dlq_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    original_event_id BIGINT NOT NULL,
    payment_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_payload JSON,
    failure_reason TEXT NOT NULL,
    retry_attempts INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    resolution_notes TEXT,
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    
    INDEX idx_payment_id (payment_id),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_resolved (resolved_at)
) ENGINE=InnoDB;

CREATE TABLE refunds (
    refund_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    payment_id BIGINT NOT NULL,
    order_id BIGINT NOT NULL,
    
    refund_amount DECIMAL(12,2) NOT NULL,
    refund_reason ENUM('customer_request', 'fraud', 'duplicate', 'product_issue', 'other') NOT NULL,
    refund_notes TEXT,
    
    gateway_refund_id VARCHAR(255),
    
    status ENUM('pending', 'processing', 'succeeded', 'failed', 'cancelled') NOT NULL DEFAULT 'pending',
    
    -- NEW: Item-level refund tracking
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
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB;

-- NEW: Track refunds at line-item level for partial refunds
CREATE TABLE refund_items (
    refund_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    refund_id BIGINT NOT NULL,
    order_item_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    refund_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (refund_id) REFERENCES refunds(refund_id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id),
    
    INDEX idx_refund_id (refund_id),
    INDEX idx_order_item_id (order_item_id)
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
-- ARCHIVAL WITH LOCATION TRACKING
-- ============================================

-- NEW: Fast lookup cache for archived orders
CREATE TABLE order_archive_index (
    order_id BIGINT PRIMARY KEY,
    location ENUM('active', 'archived', 'cold_storage') NOT NULL DEFAULT 'active',
    archived_at TIMESTAMP NULL,
    cold_storage_path VARCHAR(500),  -- S3/GCS path if in cold storage
    
    INDEX idx_location (location),
    INDEX idx_archived_at (archived_at)
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
    status ENUM('in_progress', 'completed', 'failed') NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    
    INDEX idx_archive_date (archive_date),
    INDEX idx_status (status)
) ENGINE=InnoDB;
```

#### 2. Enhanced Multi-Warehouse Service with Smart Allocation

```python
from typing import List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal

@dataclass
class WarehouseAllocation:
    warehouse_id: int
    warehouse_code: str
    quantity: int
    distance_km: float
    shipping_cost: Decimal

@dataclass
class AllocationStrategy:
    """Configuration for allocation optimization"""
    prefer_single_warehouse: bool = True
    single_warehouse_distance_penalty_km: float = 50.0  # Tolerate 50km extra for single warehouse
    max_split_shipments: int = 2
    cost_weight: float = 0.7  # 70% cost optimization
    speed_weight: float = 0.3  # 30% delivery speed

class MultiWarehouseInventoryService:
    
    async def reserve_stock_multi_warehouse(
        self,
        product_id: int,
        quantity: int,
        customer_id: int,
        shipping_address: Address,
        order_id: Optional[int] = None,
        ttl_seconds: int = 900,
        strategy: AllocationStrategy = AllocationStrategy()
    ) -> List[WarehouseAllocation]:
        """
        Intelligently allocate stock with cost optimization.
        
        NEW FEATURES:
        - Prefers single-warehouse fulfillment even if slightly farther
        - Calculates total shipping cost including split-shipment penalty
        - Limits number of split shipments
        - Allows reallocation if customer changes address
        """
        customer_coords = await self._get_cached_geocode(shipping_address)
        
        async with self.db.transaction():
            available_warehouses = await self._get_available_warehouses(
                product_id, quantity
            )
            
            if not available_warehouses:
                raise InsufficientStockError(f"Product {product_id} out of stock")
            
            # Calculate distances and costs
            warehouses_scored = await self._score_warehouses(
                available_warehouses,
                customer_coords,
                quantity,
                strategy
            )
            
            # Try single-warehouse fulfillment first
            single_wh_options = [
                wh for wh in warehouses_scored 
                if wh['available_quantity'] >= quantity
            ]
            
            if single_wh_options:
                best_single = single_wh_options[0]
                
                # Check if split would save significant cost/distance
                split_allocation = self._calculate_split_allocation(
                    warehouses_scored, quantity, strategy
                )
                
                # Prefer single warehouse unless split saves > threshold
                if self._should_prefer_single_warehouse(
                    best_single, split_allocation, strategy
                ):
                    allocations = await self._reserve_from_warehouse(
                        best_single, product_id, quantity, 
                        customer_id, order_id, ttl_seconds
                    )
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
            
            return allocations
    
    async def reallocate_on_address_change(
        self,
        order_id: int,
        new_shipping_address: Address
    ) -> bool:
        """
        Reallocate warehouse when customer changes shipping address.
        
        Strategy:
        1. Check if order is still in 'confirmed' or 'pending_payment' status
        2. Calculate new optimal allocation
        3. If significantly better (>25% cost/distance savings), reallocate
        4. Otherwise, honor original allocation to avoid churn
        """
        async with self.db.transaction():
            # Get order and current allocations
            order = await self.db.execute(
                """
                SELECT order_id, status, fulfillment_warehouse_id
                FROM orders
                WHERE order_id = ?
                FOR UPDATE
                """,
                (order_id,)
            )
            
            # Only reallocate if not yet shipped
            if order.status not in ['confirmed', 'pending_payment', 'payment_processing']:
                return False
            
            current_reservations = await self.db.execute(
                """
                SELECT warehouse_id, product_id, quantity
                FROM inventory_reservations
                WHERE order_id = ? AND status = 'active'
                """,
                (order_id,)
            )
            
            new_coords = await self._get_cached_geocode(new_shipping_address)
            
            # Calculate savings from reallocation
            current_cost = await self._calculate_shipping_cost(
                current_reservations, order.fulfillment_warehouse_id
            )
            
            # Simulate new allocation
            new_allocations = []
            for res in current_reservations:
                new_alloc = await self.reserve_stock_multi_warehouse(
                    product_id=res.product_id,
                    quantity=res.quantity,
                    customer_id=order.customer_id,
                    shipping_address=new_shipping_address,
                    order_id=None,  # Dry run
                    ttl_seconds=900,
                    strategy=AllocationStrategy(prefer_single_warehouse=True)
                )
                new_allocations.extend(new_alloc)
            
            new_cost = sum(a.shipping_cost for a in new_allocations)
            savings_pct = (current_cost - new_cost) / current_cost if current_cost > 0 else 0
            
            # Reallocate if savings > 25%
            if savings_pct > 0.25:
                # Cancel current reservations
                await self.db.execute(
                    """
                    UPDATE inventory_reservations
                    SET status = 'reallocated',
                        reallocation_reason = 'address_change_optimization'
                    WHERE order_id = ? AND status = 'active'
                    """,
                    (order_id,)
                )
                
                # Release reserved quantities
                for res in current_reservations:
                    await self.db.execute(
                        """
                        UPDATE warehouse_inventory
                        SET reserved_quantity = GREATEST(0, reserved_quantity - ?)
                        WHERE warehouse_id = ? AND product_id = ?
                        """,
                        (res.quantity, res.warehouse_id, res.product_id)
                    )
                
                # Create new reservations
                for res in current_reservations:
                    await self.reserve_stock_multi_warehouse(
                        product_id=res.product_id,
                        quantity=res.quantity,
                        customer_id=order.customer_id,
                        shipping_address=new_shipping_address,
                        order_id=order_id,
                        ttl_seconds=900
                    )
                
                return True
            
            # Keep original allocation
            return False
    
    def _should_prefer_single_warehouse(
        self,
        single_wh: dict,
        split_allocation: List[dict],
        strategy: AllocationStrategy
    ) -> bool:
        """
        Decide if single warehouse is better than split.
        
        Factors:
        - Distance penalty for single warehouse
        - Total shipping cost including split-shipment overhead
        """
        if not split_allocation:
            return True
        
        single_distance = single_wh['distance_km']
        single_cost = single_wh['shipping_cost_base']
        
        split_total_distance = sum(w['distance_km'] for w in split_allocation)
        split_total_cost = sum(w['shipping_cost_base'] for w in split_allocation)
        # Add split shipment penalty (multiple carrier pickups)
        split_total_cost *= 1.25  # 25% overhead for split shipments
        
        # Weighted score
        single_score = (
            strategy.cost_weight * single_cost + 
            strategy.speed_weight * single_distance
        )
        split_score = (
            strategy.cost_weight * split_total_cost + 
            strategy.speed_weight * split_total_distance
        )
        
        return single_score <= split_score * 1.15  # Prefer single if within 15%
    
    async def _get_cached_geocode(self, address: Address) -> Tuple[float, float]:
        """
        Geocode with permanent caching in DB.
        
        IMPROVEMENT: Store geocoded addresses in database instead of Redis
        for permanent caching without TTL concerns.
        """
        cache_key = f"{address.postal_code}:{address.country}"
        
        # Check database cache
        cached = await self.db.execute(
            """
            SELECT latitude, longitude
            FROM geocode_cache
            WHERE postal_code = ? AND country = ?
            """,
            (address.postal_code, address.country)
        )
        
        if cached:
            return (cached.latitude, cached.longitude)
        
        # Geocode via external service
        coords = await self.geocoding_service.geocode(
            f"{address.city}, {address.state} {address.postal_code}, {address.country}"
        )
        
        # Store permanently
        await self.db.execute(
            """
            INSERT INTO geocode_cache (postal_code, country, latitude, longitude)
            VALUES (?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE latitude = ?, longitude = ?
            """,
            (address.postal_code, address.country, coords[0], coords[1],
             coords[0], coords[1])
        )
        
        return coords

# Add geocode cache table
"""
CREATE TABLE geocode_cache (
    cache_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_postal_country (postal_code, country),
    INDEX idx_country (country)
) ENGINE=InnoDB;
"""
```

#### 3. Resilient Payment Service with DLQ & Exponential Backoff

```python
from typing import Optional
import asyncio
from datetime import datetime, timedelta

class PaymentService:
    
    MAX_RETRY_ATTEMPTS = 5
    BASE_RETRY_DELAY = 30  # seconds
    
    async def process_payment_event(self, event_id: int):
        """
        Process payment event with automatic retry and DLQ.
        
        IMPROVEMENTS:
        - Exponential backoff with jitter
        - Dead letter queue after max retries
        - Configurable retry strategy per event type
        """
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
                    p.status as payment_status
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
                # Process based on event type
                if event.event_type == 'authorization_succeeded':
                    await self._handle_authorization_success(event)
                elif event.event_type == 'capture_succeeded':
                    await self._handle_capture_success(event)
                elif event.event_type == 'authorization_failed':
                    await self._handle_authorization_failure(event)
                elif event.event_type == 'refund_succeeded':
                    await self._handle_refund_success(event)
                
                # Mark as processed
                await self.db.execute(
                    """
                    UPDATE payment_events
                    SET processed = TRUE,
                        processed_at = NOW()
                    WHERE event_id = ?
                    """,
                    (event_id,)
                )
                
            except Exception as e:
                await self._handle_event_failure(event, e)
                raise
    
    async def _handle_event_failure(self, event, error: Exception):
        """
        Handle failed event processing with retry or DLQ.
        """
        retry_count = event.retry_count + 1
        
        if retry_count >= self.MAX_RETRY_ATTEMPTS:
            # Move to dead letter queue
            await self.db.execute(
                """
                INSERT INTO payment_events_dlq (
                    original_event_id,
                    payment_id,
                    event_type,
                    event_payload,
                    failure_reason,
                    retry_attempts
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (event.event_id, event.payment_id, event.event_type,
                 event.event_payload, str(error), retry_count)
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
            
            # Alert operations team
            await self.alerting_service.send_alert(
                severity='high',
                message=f"Payment event {event.event_id} moved to DLQ after {retry_count} attempts",
                details={'event_id': event.event_id, 'payment_id': event.payment_id}
            )
        else:
            # Schedule retry with exponential backoff + jitter
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
            
            # Increment payment retry counter
            await self.db.execute(
                """
                UPDATE payments
                SET retry_count = retry_count + 1
                WHERE payment_id = ?
                """,
                (event.payment_id,)
            )
            
            # Log retry event
            await self._log_payment_event(
                event.payment_id,
                'retry_scheduled',
                {
                    'original_event_id': event.event_id,
                    'retry_count': retry_count,
                    'next_retry_at': next_retry_at.isoformat(),
                    'error': str(error)
                }
            )
    
    def _calculate_retry_delay(self, retry_count: int) -> int:
        """
        Exponential backoff with jitter: delay = base * 2^retry + random(0, base)
        
        Examples:
        - Retry 1: 30-60 seconds
        - Retry 2: 60-90 seconds  
        - Retry 3: 120-150 seconds
        - Retry 4: 240-270 seconds
        - Retry 5: 480-510 seconds
        """
        import random
        base_delay = self.BASE_RETRY_DELAY * (2 ** (retry_count - 1))
        jitter = random.randint(0, self.BASE_RETRY_DELAY)
        return base_delay + jitter
    
    async def process_retry_queue(self):
        """
        Background worker to process scheduled retries.
        Runs every 10 seconds.
        """
        while True:
            try:
                # Find events ready for retry
                events_to_retry = await self.db.execute(
                    """
                    SELECT event_id
                    FROM payment_events
                    WHERE processed = FALSE
                        AND next_retry_at IS NOT NULL
                        AND next_retry_at <= NOW()
                    LIMIT 100
                    """
                )
                
                for event in events_to_retry:
                    # Process asynchronously
                    asyncio.create_task(
                        self.process_payment_event(event.event_id)
                    )
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"Error in retry queue processor: {e}")
                await asyncio.sleep(30)  # Back off on error
    
    async def _handle_refund_success(self, event):
        """
        Handle successful refund with item-level tracking.
        """
        payload = json.loads(event.event_payload)
        refund_id = payload.get('refund_id')
        
        async with self.db.transaction():
            # Get refund details
            refund = await self.db.execute(
                """
                SELECT 
                    r.refund_id,
                    r.order_id,
                    r.refund_amount,
                    r.is_full_refund
                FROM refunds r
                WHERE r.refund_id = ?
                FOR UPDATE
                """,
                (refund_id,)
            )
            
            # Update payment status
            await self.db.execute(
                """
                UPDATE payments
                SET status = IF(
                    (SELECT SUM(refund_amount) FROM refunds WHERE payment_id = ?) >= amount,
                    'refunded',
                    'partially_refunded'
                )
                WHERE payment_id = ?
                """,
                (event.payment_id, event.payment_id)
            )
            
            # Update order
            if refund.is_full_refund:
                await self.db.execute(
                    """
                    UPDATE orders
                    SET status = 'refunded',
                        refunded_amount = total_amount
                    WHERE order_id = ?
                    """,
                    (refund.order_id,)
                )
            else:
                # Partial refund - update order items
                refund_items = await self.db.execute(
                    """
                    SELECT order_item_id, quantity, refund_amount
                    FROM refund_items
                    WHERE refund_id = ?
                    """,
                    (refund_id,)
                )
                
                for item in refund_items:
                    await self.db.execute(
                        """
                        UPDATE order_items
                        SET refunded_quantity = refunded_quantity + ?,
                            refunded_amount = refunded_amount + ?
                        WHERE order_item_id = ?
                        """,
                        (item.quantity, item.refund_amount, item.order_item_id)
                    )
                
                # Update order status and refunded amount
                await self.db.execute(
                    """
                    UPDATE orders
                    SET status = 'partially_refunded',
                        refunded_amount = refunded_amount + ?
                    WHERE order_id = ?
                    """,
                    (refund.refund_amount, refund.order_id)
                )
```

#### 4. Optimized Archive Service with Index Cache

```python
class OrderArchiveService:
    
    async def query_order(self, order_id: int) -> Optional[Order]:
        """
        Query order with O(1) location lookup using archive index.
        
        IMPROVEMENT: Use archive_index table instead of Redis for permanent,
        consistent location tracking.
        """
        # Check location index first (in-memory cache + DB)
        location = await self._get_order_location(order_id)
        
        if location == 'active':
            order = await self.db.execute(
                """
                SELECT * FROM orders
                WHERE order_id = ? AND deleted_at IS NULL
                """,
                (order_id,)
            )
        elif location == 'archived':
            order = await self.db.execute(
                """
                SELECT * FROM orders_archive
                WHERE order_id = ?
                """,
                (order_id,)
            )
        elif location == 'cold_storage':
            # Fetch from S3/GCS (slower, rare case)
            storage_path = await self.db.execute(
                """
                SELECT cold_storage_path
                FROM order_archive_index
                WHERE order_id = ?
                """,
                (order_id,)
            )
            order = await self._fetch_from_cold_storage(storage_path.cold_storage_path)
        else:
            # Not yet indexed - check both tables
            order = await self._check_both_tables(order_id)
        
        return order
    
    async def _get_order_location(self, order_id: int) -> Optional[str]:
        """
        Get order location from index with in-memory cache.
        """
        # Check in-memory cache (Redis)
        cache_key = f"order_location:{order_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached
        
        # Query database index
        result = await self.db.execute(
            """
            SELECT location
            FROM order_archive_index
            WHERE order_id = ?
            """,
            (order_id,)
        )
        
        if result:
            # Cache for 24 hours (location rarely changes)
            await self.cache.setex(cache_key, 86400, result.location)
            return result.location
        
        return None
    
    async def archive_old_orders(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000
    ) -> int:
        """
        Archive with index population.
        """
        terminal_states = ['delivered', 'cancelled', 'refunded', 'partially_refunded']
        total_archived = 0
        
        batch_id = await self._create_archive_batch(cutoff_date)
        
        try:
            while True:
                async with self.db.transaction():
                    orders = await self.db.execute(
                        """
                        SELECT order_id
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
                    
                    # Copy to archive tables
                    await self._copy_to_archive(order_ids)
                    
                    # Populate archive index
                    await self.db.execute(
                        """
                        INSERT INTO order_archive_index (order_id, location, archived_at)
                        VALUES {}
                        ON DUPLICATE KEY UPDATE location = 'archived', archived_at = NOW()
                        """.format(','.join(['(?, "archived", NOW())'] * len(order_ids))),
                        order_ids
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
            return total_archived
            
        except Exception as e:
            await self._fail_batch(batch_id)
            raise
    
    async def _copy_to_archive(self, order_ids: List[int]):
        """Copy orders and related data to archive tables"""
        await self.db.execute(
            """
            INSERT INTO orders_archive
            SELECT * FROM orders
            WHERE order_id IN ({})
            """.format(','.join('?' * len(order_ids))),
            order_ids
        )
        
        await self.db.execute(
            """
            INSERT INTO order_items_archive
            SELECT * FROM order_items
            WHERE order_id IN ({})
            """.format(','.join('?' * len(order_ids))),
            order_ids
        )
        
        await self.db.execute(
            """
            INSERT INTO order_status_history_archive
            SELECT * FROM order_status_history
            WHERE order_id IN ({})
            """.format(','.join('?' * len(order_ids))),
            order_ids
        )
```

## What I Improved

1. **Payment Event Resilience**: Added `payment_events_dlq` table, exponential backoff with jitter, and automatic retry scheduling. Events that fail 5 times move to DLQ with alerting instead of silently failing.

2. **Item-Level Refund Tracking**: Added `refund_items` table and `refunded_quantity`/`refunded_amount` columns to `order_items` for granular partial refund tracking. This enables accurate financial reporting and inventory restocking decisions.

3. **Smart Warehouse Allocation**: Enhanced algorithm to prefer single-warehouse fulfillment using weighted scoring (cost + distance). Added 25% split-shipment penalty and configurable thresholds to avoid unnecessary splits.

4. **Address Change Reallocation**: New `reallocate_on_address_change()` method that intelligently decides whether to reallocate based on 25% cost savings threshold. Prevents excessive reallocation churn while optimizing significant changes.

5. **Inventory Transfer Tracking**: Added `inventory_transfers` table to track warehouse-to-warehouse movements, enabling better inventory distribution and rebalancing strategies.

6. **Archive Index for O(1) Lookup**: Added `order_archive_index` table with location tracking to eliminate expensive double-table queries. Cached in Redis with 24-hour TTL for sub-millisecond lookups.

7. **Split Shipment Support**: Added `shipments` table, `is_split_shipment` flag, `partially_shipped` status, and `shipment_id` foreign key in `order_items` to properly track multi-warehouse fulfillments.

8. **Permanent Geocode Caching**: Replaced Redis-only geocoding cache with `geocode_cache` database table for permanent storage without TTL concerns.

9. **Enhanced Order States**: Added `partially_shipped` and `partially_refunded` statuses for accurate order lifecycle tracking.

10. **Retry Metrics**: Added `retry_count` columns to both `payments` and `payment_events` tables to identify problematic integrations and trigger alerts.

## What I Kept

1. **Core Schema Structure**: Original tables (customers, products, orders, order_items) remain unchanged—excellent foundation.

2. **Optimistic Locking**: Version columns on critical tables for concurrency control.

3. **Comprehensive Indexing**: All original indexes plus targeted additions for new query patterns.

4. **Two-Phase Inventory Reservation**: Reserve → confirm pattern with TTL-based expiration.

5. **Webhook Signature Verification**: HMAC-based security to prevent fraudulent webhooks.

6. **Event Sourcing Pattern**: `payment_events` table captures complete payment lifecycle.

7. **Soft Delete Strategy**: `deleted_at` for safe archival with recovery option.

8. **Financial Audit Trail**: Immutable order snapshots and status history.

9. **Background Cleanup Jobs**: Expired reservation cleanup and abandoned cart handling.

10. **Compressed Archive Tables**: ROW_FORMAT=COMPRESSED for cost-efficient storage.

## Remaining Concerns

1. **Geocoding API Rate Limits**: The permanent cache mitigates this, but new addresses still require API calls. Should we pre-populate cache with known zip code centroids?

2. **DLQ Processing**: Who monitors and resolves DLQ entries? Need operational runbook for manual intervention and replay mechanism.

3. **Split Shipment Customer Communication**: How do we notify customers about partial shipments? Need email template system and shipment tracking links.

4. **Warehouse Capacity Planning**: `max_daily_orders` field exists but no enforcement logic. Should allocation algorithm respect capacity limits during peak seasons?

5. **International Shipping Complexity**: Distance-based allocation assumes domestic shipping. International orders need customs, duties, and carrier compatibility considerations.

6. **Archive Index Consistency**: What ensures `order_archive_index` stays synchronized during failures? Need reconciliation job to validate index accuracy.

## Convergence Status

**ITERATING** - Enhanced resilience, cost optimization, and operational observability, but need clarity on DLQ operations and split-shipment customer experience.

## PROMPT_FOR_ARCHITECT:

Please focus on:

1. **DLQ Operational Model**: How should operations teams monitor and resolve DLQ entries? Should we build admin UI for manual replay, or automatic replay after investigating root cause? What metrics trigger alerts?

2. **Warehouse Capacity Enforcement**: Should the allocation algorithm hard-fail when warehouse exceeds `max_daily_orders`, or gracefully overflow to next-best warehouse? How do we handle Black Friday scenarios?

3. **Archive Index Recovery**: If archive index gets out of sync (e.g., partial transaction failure), what's the recovery strategy? Should we run nightly reconciliation comparing `orders.order_id` vs `order_archive_index.order_id`?

4. **Cost vs. Speed Trade-off Configuration**: Should the `AllocationStrategy` weights be customer-configurable (e.g., "expedited shipping" prefers speed, "economy" prefers cost), or system-wide configuration?

**Convergence Signal:** ITERATING

---

## Round 3

### 🔵 Agent A

## Design

### E-Commerce Order System - Production-Ready Schema with Operational Excellence

#### 1. Core Schema with Enhanced Operational Controls

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
    
    -- Capacity planning with soft/hard limits
    max_daily_orders INT,
    capacity_buffer_pct DECIMAL(5,2) NOT NULL DEFAULT 10.00,  -- NEW: 10% buffer for overflow
    current_daily_orders INT NOT NULL DEFAULT 0,
    capacity_reset_date DATE NOT NULL,
    
    shipping_cost_base DECIMAL(8,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status_priority (status, priority),
    INDEX idx_location (latitude, longitude),
    INDEX idx_capacity_date (capacity_reset_date, current_daily_orders)  -- NEW: Track daily usage
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

-- NEW: Pre-populated geocode cache with zip code centroids
CREATE TABLE geocode_cache (
    cache_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate') NOT NULL DEFAULT 'approximate',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_postal_country (postal_code, country),
    INDEX idx_country (country),
    INDEX idx_quality (geocode_quality)
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
    shipping_preference ENUM('standard', 'expedited', 'economy') NOT NULL DEFAULT 'standard',  -- NEW: Customer choice
    
    -- Shipping information (immutable snapshot)
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country CHAR(2),
    shipping_latitude DECIMAL(10,8),
    shipping_longitude DECIMAL(11,8),
    
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
    INDEX idx_shipping_preference (shipping_preference, status)  -- NEW: Query by preference
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
    tracking_url VARCHAR(500),  -- NEW: Pre-built tracking link for customer emails
    
    status ENUM('pending', 'picked', 'packed', 'shipped', 'in_transit', 'delivered', 'failed') 
        NOT NULL DEFAULT 'pending',
    
    shipping_cost DECIMAL(10,2),
    estimated_delivery_date DATE,
    actual_delivery_date DATE,
    
    -- NEW: Customer notification tracking
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
    INDEX idx_notification_status (notification_sent, status)  -- NEW: Find pending notifications
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

-- NEW: Dead letter queue with operational workflow
CREATE TABLE payment_events_dlq (
    dlq_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    original_event_id BIGINT NOT NULL,
    payment_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_payload JSON,
    failure_reason TEXT NOT NULL,
    retry_attempts INT NOT NULL,
    
    -- Operational workflow
    status ENUM('pending_review', 'investigating', 'ready_for_replay', 'replayed', 'discarded') 
        NOT NULL DEFAULT 'pending_review',
    assigned_to VARCHAR(100),  -- Operations team member
    priority ENUM('low', 'medium', 'high', 'critical') NOT NULL DEFAULT 'medium',
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP NULL,
    resolved_at TIMESTAMP NULL,
    replayed_at TIMESTAMP NULL,
    resolution_notes TEXT,
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    
    INDEX idx_payment_id (payment_id),
    INDEX idx_status_priority (status, priority, created_at),  -- NEW: Ops queue
    INDEX idx_assigned_to (assigned_to, status),  -- NEW: Team member workload
    INDEX idx_created_at (created_at DESC),
    INDEX idx_resolved (resolved_at)
) ENGINE=InnoDB;

-- NEW: DLQ metrics for monitoring
CREATE TABLE dlq_metrics_daily (
    metric_date DATE PRIMARY KEY,
    total_entries INT NOT NULL DEFAULT 0,
    pending_review INT NOT NULL DEFAULT 0,
    investigating INT NOT NULL DEFAULT 0,
    ready_for_replay INT NOT NULL DEFAULT 0,
    replayed_today INT NOT NULL DEFAULT 0,
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
    refund_reason ENUM('customer_request', 'fraud', 'duplicate', 'product_issue', 'other') NOT NULL,
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
    INDEX idx_created_at (created_at DESC)
) ENGINE=InnoDB;

CREATE TABLE refund_items (
    refund_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    refund_id BIGINT NOT NULL,
    order_item_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    refund_amount DECIMAL(10,2) NOT NULL,
    restock BOOLEAN NOT NULL DEFAULT TRUE,  -- NEW: Should item be restocked?
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (refund_id) REFERENCES refunds(refund_id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id),
    
    INDEX idx_refund_id (refund_id),
    INDEX idx_order_item_id (order_item_id),
    INDEX idx_restock (restock, created_at)  -- NEW: Find items to restock
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
-- ARCHIVE SYSTEM WITH RECONCILIATION
-- ============================================

CREATE TABLE order_archive_index (
    order_id BIGINT PRIMARY KEY,
    location ENUM('active', 'archived', 'cold_storage') NOT NULL DEFAULT 'active',
    archived_at TIMESTAMP NULL,
    cold_storage_path VARCHAR(500),
    
    -- NEW: Reconciliation tracking
    last_verified_at TIMESTAMP NULL,
    verification_status ENUM('ok', 'missing', 'duplicate', 'inconsistent') NOT NULL DEFAULT 'ok',
    
    INDEX idx_location (location),
    INDEX idx_archived_at (archived_at),
    INDEX idx_verification (verification_status, last_verified_at)  -- NEW: Find unverified records
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
    status ENUM('in_progress', 'completed', 'failed', 'verified') NOT NULL,  -- NEW: Added verified
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    verified_at TIMESTAMP NULL,  -- NEW: When reconciliation completed
    
    INDEX idx_archive_date (archive_date),
    INDEX idx_status (status),
    INDEX idx_verification (status, verified_at)  -- NEW: Find unverified batches
) ENGINE=InnoDB;

-- NEW: Reconciliation audit log
CREATE TABLE archive_reconciliation_log (
    log_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    batch_id BIGINT NULL,
    reconciliation_type ENUM('full_scan', 'batch_verification', 'spot_check') NOT NULL,
    orders_checked INT NOT NULL,
    discrepancies_found INT NOT NULL,
    discrepancies_resolved INT NOT NULL,
    execution_time_ms INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (batch_id) REFERENCES archive_batches(batch_id),
    
    INDEX idx_created_at (created_at DESC),
    INDEX idx_type_date (reconciliation_type, created_at)
) ENGINE=InnoDB;
```

#### 2. Enhanced Multi-Warehouse Service with Capacity Management

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
    capacity_status: str  # 'available', 'buffer', 'overflow'

@dataclass
class AllocationStrategy:
    """Customer-configurable allocation strategy based on shipping preference"""
    shipping_preference: str  # 'standard', 'expedited', 'economy'
    prefer_single_warehouse: bool = True
    max_split_shipments: int = 2
    
    @property
    def cost_weight(self) -> float:
        """Cost optimization weight based on shipping preference"""
        return {'economy': 0.9, 'standard': 0.7, 'expedited': 0.3}[self.shipping_preference]
    
    @property
    def speed_weight(self) -> float:
        """Delivery speed weight based on shipping preference"""
        return {'economy': 0.1, 'standard': 0.3, 'expedited': 0.7}[self.shipping_preference]

class MultiWarehouseInventoryService:
    
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
        """
        Intelligently allocate stock with capacity-aware optimization.
        
        NEW FEATURES:
        - Respects warehouse capacity limits with graceful overflow
        - Uses customer shipping preference for allocation weights
        - Tracks capacity status in allocation result
        """
        if strategy is None:
            strategy = AllocationStrategy(shipping_preference='standard')
        
        customer_coords = await self._get_cached_geocode(shipping_address)
        
        async with self.db.transaction():
            # Reset daily counters if needed
            await self._reset_warehouse_capacity_if_needed()
            
            available_warehouses = await self._get_available_warehouses_with_capacity(
                product_id, quantity
            )
            
            if not available_warehouses:
                raise InsufficientStockError(f"Product {product_id} out of stock")
            
            # Calculate distances, costs, and capacity status
            warehouses_scored = await self._score_warehouses(
                available_warehouses,
                customer_coords,
                quantity,
                strategy
            )
            
            # Try single-warehouse fulfillment first
            single_wh_options = [
                wh for wh in warehouses_scored 
                if wh['available_quantity'] >= quantity
                and wh['capacity_status'] != 'overflow'  # Prefer warehouses with capacity
            ]
            
            if single_wh_options:
                best_single = single_wh_options[0]
                
                # Check if split would save significant cost/distance
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
            
            # Increment capacity for all warehouses used
            for alloc in allocations:
                await self._increment_warehouse_capacity(alloc.warehouse_id)
            
            return allocations
    
    async def _get_available_warehouses_with_capacity(
        self,
        product_id: int,
        quantity: int
    ) -> List[dict]:
        """
        Get warehouses with stock, annotated with capacity status.
        
        Capacity tiers:
        - 'available': current_daily_orders < max_daily_orders
        - 'buffer': current_daily_orders >= max_daily_orders AND < (max * (1 + buffer_pct))
        - 'overflow': current_daily_orders >= (max * (1 + buffer_pct))
        """
        return await self.db.execute(
            """
            SELECT 
                w.warehouse_id,
                w.warehouse_code,
                w.latitude,
                w.longitude,
                w.shipping_cost_base,
                w.priority,
                w.max_daily_orders,
                w.current_daily_orders,
                w.capacity_buffer_pct,
                wi.stock_quantity - wi.reserved_quantity as available_quantity,
                CASE
                    WHEN w.max_daily_orders IS NULL THEN 'available'
                    WHEN w.current_daily_orders < w.max_daily_orders THEN 'available'
                    WHEN w.current_daily_orders < (w.max_daily_orders * (1 + w.capacity_buffer_pct / 100)) THEN 'buffer'
                    ELSE 'overflow'
                END as capacity_status
            FROM warehouses w
            JOIN warehouse_inventory wi 
                ON w.warehouse_id = wi.warehouse_id
            WHERE w.status = 'active'
                AND wi.product_id = ?
                AND (wi.stock_quantity - wi.reserved_quantity) > 0
            ORDER BY 
                CASE capacity_status
                    WHEN 'available' THEN 1
                    WHEN 'buffer' THEN 2
                    WHEN 'overflow' THEN 3
                END,
                w.priority ASC
            """,
            (product_id,)
        )
    
    async def _reset_warehouse_capacity_if_needed(self):
        """
        Reset daily capacity counters at midnight UTC.
        """
        today = date.today()
        
        await self.db.execute(
            """
            UPDATE warehouses
            SET current_daily_orders = 0,
                capacity_reset_date = ?
            WHERE capacity_reset_date < ?
            """,
            (today, today)
        )
    
    async def _increment_warehouse_capacity(self, warehouse_id: int):
        """
        Increment daily order counter for capacity tracking.
        """
        await self.db.execute(
            """
            UPDATE warehouses
            SET current_daily_orders = current_daily_orders + 1
            WHERE warehouse_id = ?
            """,
            (warehouse_id,)
        )
    
    async def _score_warehouses(
        self,
        warehouses: List[dict],
        customer_coords: Tuple[float, float],
        quantity: int,
        strategy: AllocationStrategy
    ) -> List[dict]:
        """
        Score and rank warehouses using customer-driven weights.
        
        NEW: Capacity status affects scoring:
        - 'available': no penalty
        - 'buffer': 5% cost penalty
        - 'overflow': 15% cost penalty (discourage but allow)
        """
        scored = []
        
        for wh in warehouses:
            distance = self._calculate_distance(
                (wh['latitude'], wh['longitude']),
                customer_coords
            )
            
            base_cost = wh['shipping_cost_base']
            
            # Apply capacity penalty
            capacity_multiplier = {
                'available': 1.0,
                'buffer': 1.05,
                'overflow': 1.15
            }[wh['capacity_status']]
            
            adjusted_cost = base_cost * capacity_multiplier
            
            # Weighted score (lower is better)
            score = (
                strategy.cost_weight * adjusted_cost +
                strategy.speed_weight * distance
            )
            
            wh['distance_km'] = distance
            wh['score'] = score
            wh['adjusted_cost'] = adjusted_cost
            scored.append(wh)
        
        # Sort by score (best first)
        return sorted(scored, key=lambda x: x['score'])
    
    async def reallocate_on_address_change(
        self,
        order_id: int,
        new_shipping_address: Address
    ) -> bool:
        """
        Reallocate warehouse when customer changes shipping address.
        
        Only reallocates if savings > 25% AND order not yet shipped.
        """
        async with self.db.transaction():
            order = await self.db.execute(
                """
                SELECT 
                    o.order_id, 
                    o.status, 
                    o.fulfillment_warehouse_id,
                    o.customer_id,
                    o.shipping_preference
                FROM orders o
                WHERE order_id = ?
                FOR UPDATE
                """,
                (order_id,)
            )
            
            # Only reallocate before shipping
            if order.status not in ['confirmed', 'pending_payment', 'payment_processing']:
                return False
            
            current_reservations = await self.db.execute(
                """
                SELECT warehouse_id, product_id, quantity
                FROM inventory_reservations
                WHERE order_id = ? AND status = 'active'
                """,
                (order_id,)
            )
            
            # Calculate current cost
            current_cost = await self._calculate_total_shipping_cost(
                current_reservations
            )
            
            # Simulate new allocation
            strategy = AllocationStrategy(
                shipping_preference=order.shipping_preference,
                prefer_single_warehouse=True
            )
            
            new_total_cost = Decimal(0)
            for res in current_reservations:
                # Dry-run allocation
                new_alloc = await self._simulate_allocation(
                    product_id=res.product_id,
                    quantity=res.quantity,
                    shipping_address=new_shipping_address,
                    strategy=strategy
                )
                new_total_cost += sum(a.shipping_cost for a in new_alloc)
            
            # Only reallocate if savings > 25%
            savings_pct = (current_cost - new_total_cost) / current_cost if current_cost > 0 else 0
            
            if savings_pct > 0.25:
                # Cancel current reservations
                await self._cancel_reservations(order_id, reason='address_change_optimization')
                
                # Create new reservations
                for res in current_reservations:
                    await self.reserve_stock_multi_warehouse(
                        product_id=res.product_id,
                        quantity=res.quantity,
                        customer_id=order.customer_id,
                        shipping_address=new_shipping_address,
                        order_id=order_id,
                        ttl_seconds=900,
                        strategy=strategy
                    )
                
                return True
            
            return False
    
    async def _get_cached_geocode(self, address: Address) -> Tuple[float, float]:
        """
        Geocode with permanent database caching.
        
        Falls back to approximate centroid if high-quality geocode unavailable.
        """
        cache_key = f"{address.postal_code}:{address.country}"
        
        # Check in-memory cache (Redis) first
        cached = await self.cache.get(cache_key)
        if cached:
            return tuple(map(float, cached.split(',')))
        
        # Check database cache
        db_cached = await self.db.execute(
            """
            SELECT latitude, longitude, geocode_quality
            FROM geocode_cache
            WHERE postal_code = ? AND country = ?
            """,
            (address.postal_code, address.country)
        )
        
        if db_cached:
            # Cache in Redis for 24 hours
            await self.cache.setex(
                cache_key, 
                86400, 
                f"{db_cached.latitude},{db_cached.longitude}"
            )
            return (db_cached.latitude, db_cached.longitude)
        
        # Geocode via external service
        try:
            coords, quality = await self.geocoding_service.geocode_with_quality(
                f"{address.city}, {address.state} {address.postal_code}, {address.country}"
            )
        except GeocodingError:
            # Fall back to approximate centroid
            coords, quality = await self._get_approximate_centroid(
                address.postal_code, address.country
            )
        
        # Store permanently
        await self.db.execute(
            """
            INSERT INTO geocode_cache (postal_code, country, latitude, longitude, geocode_quality)
            VALUES (?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE 
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                geocode_quality = VALUES(geocode_quality),
                updated_at = NOW()
            """,
            (address.postal_code, address.country, coords[0], coords[1], quality)
        )
        
        # Cache in Redis
        await self.cache.setex(cache_key, 86400, f"{coords[0]},{coords[1]}")
        
        return coords
```

#### 3. Payment Service with Operational DLQ Management

```python
from typing import Optional
import asyncio
from datetime import datetime, timedelta
from enum import Enum

class DLQPriority(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

class PaymentService:
    
    MAX_RETRY_ATTEMPTS = 5
    BASE_RETRY_DELAY = 30  # seconds
    
    async def process_payment_event(self, event_id: int):
        """
        Process payment event with automatic retry and DLQ.
        """
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
                    p.status as payment_status,
                    p.amount
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
                # Process based on event type
                if event.event_type == 'authorization_succeeded':
                    await self._handle_authorization_success(event)
                elif event.event_type == 'capture_succeeded':
                    await self._handle_capture_success(event)
                elif event.event_type == 'authorization_failed':
                    await self._handle_authorization_failure(event)
                elif event.event_type == 'refund_succeeded':
                    await self._handle_refund_success(event)
                
                # Mark as processed
                await self.db.execute(
                    """
                    UPDATE payment_events
                    SET processed = TRUE,
                        processed_at = NOW()
                    WHERE event_id = ?
                    """,
                    (event_id,)
                )
                
            except Exception as e:
                await self._handle_event_failure(event, e)
                raise
    
    async def _handle_event_failure(self, event, error: Exception):
        """
        Handle failed event processing with intelligent DLQ routing.
        """
        retry_count = event.retry_count + 1
        
        if retry_count >= self.MAX_RETRY_ATTEMPTS:
            # Determine priority based on event type and amount
            priority = self._calculate_dlq_priority(event)
            
            # Move to dead letter queue
            dlq_id = await self.db.execute(
                """
                INSERT INTO payment_events_dlq (
                    original_event_id,
                    payment_id,
                    event_type,
                    event_payload,
                    failure_reason,
                    retry_attempts,
                    status,
                    priority
                )
                VALUES (?, ?, ?, ?, ?, ?, 'pending_review', ?)
                """,
                (event.event_id, event.payment_id, event.event_type,
                 event.event_payload, str(error), retry_count, priority.value)
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
            
            # Update daily metrics
            await self._update_dlq_metrics()
            
            # Alert based on priority
            if priority in [DLQPriority.HIGH, DLQPriority.CRITICAL]:
                await self.alerting_service.send_alert(
                    severity='high' if priority == DLQPriority.HIGH else 'critical',
                    message=f"Payment event {event.event_id} moved to DLQ with {priority.value} priority",
                    details={
                        'event_id': event.event_id,
                        'payment_id': event.payment_id,
                        'dlq_id': dlq_id,
                        'amount': event.amount,
                        'event_type': event.event_type
                    }
                )
        else:
            # Schedule retry with exponential backoff
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
            
            await self.db.execute(
                """
                UPDATE payments
                SET retry_count = retry_count + 1
                WHERE payment_id = ?
                """,
                (event.payment_id,)
            )
    
    def _calculate_dlq_priority(self, event) -> DLQPriority:
        """
        Assign DLQ priority based on event type and payment amount.
        
        CRITICAL: capture_succeeded, refund_succeeded (money movement confirmed)
        HIGH: authorization_succeeded (customer charged, order must fulfill)
        MEDIUM: capture_failed, refund_failed (retry likely to succeed)
        LOW: webhook_received, authorization_failed (informational)
        """
        critical_events = ['capture_succeeded', 'refund_succeeded']
        high_events = ['authorization_succeeded']
        medium_events = ['capture_failed', 'refund_failed', 'capture_requested']
        
        if event.event_type in critical_events:
            return DLQPriority.CRITICAL
        elif event.event_type in high_events:
            return DLQPriority.HIGH
        elif event.event_type in medium_events:
            return DLQPriority.MEDIUM
        else:
            return DLQPriority.LOW
    
    def _calculate_retry_delay(self, retry_count: int) -> int:
        """
        Exponential backoff with jitter.
        """
        import random
        base_delay = self.BASE_RETRY_DELAY * (2 ** (retry_count - 1))
        jitter = random.randint(0, self.BASE_RETRY_DELAY)
        return base_delay + jitter
    
    async def _update_dlq_metrics(self):
        """
        Update daily DLQ metrics for monitoring dashboard.
        """
        today = date.today()
        
        metrics = await self.db.execute(
            """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending_review' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'investigating' THEN 1 ELSE 0 END) as investigating,
                SUM(CASE WHEN status = 'ready_for_replay' THEN 1 ELSE 0 END) as ready,
                SUM(CASE WHEN status = 'replayed' AND DATE(replayed_at) = ? THEN 1 ELSE 0 END) as replayed_today,
                SUM(CASE WHEN status = 'discarded' AND DATE(resolved_at) = ? THEN 1 ELSE 0 END) as discarded_today,
                SUM(CASE WHEN priority = 'critical' AND status IN ('pending_review', 'investigating') THEN 1 ELSE 0 END) as critical,
                AVG(
                    CASE 
                        WHEN resolved_at IS NOT NULL 
                        THEN TIMESTAMPDIFF(HOUR, created_at, resolved_at)
                        ELSE NULL 
                    END
                ) as avg_resolution_hours
            FROM payment_events_dlq
            WHERE created_at >= ? - INTERVAL 7 DAY
            """,
            (today, today, today)
        )
        
        await self.db.execute(
            """
            INSERT INTO dlq_metrics_daily (
                metric_date, total_entries, pending_review, investigating,
                ready_for_replay, replayed_today, discarded_today, critical_count,
                avg_resolution_hours
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON DUPLICATE KEY UPDATE
                total_entries = VALUES(total_entries),
                pending_review = VALUES(pending_review),
                investigating = VALUES(investigating),
                ready_for_replay = VALUES(ready_for_replay),
                replayed_today = VALUES(replayed_today),
                discarded_today = VALUES(discarded_today),
                critical_count = VALUES(critical_count),
                avg_resolution_hours = VALUES(avg_resolution_hours)
            """,
            (today, metrics.total, metrics.pending, metrics.investigating,
             metrics.ready, metrics.replayed_today, metrics.discarded_today,
             metrics.critical, metrics.avg_resolution_hours)
        )
    
    async def replay_dlq_entry(self, dlq_id: int, operator: str) -> bool:
        """
        Manual replay of DLQ entry by operations team.
        """
        async with self.db.transaction():
            dlq_entry = await self.db.execute(
                """
                SELECT 
                    dlq_id,
                    original_event_id,
                    payment_id,
                    event_type,
                    event_payload,
                    status
                FROM payment_events_dlq
                WHERE dlq_id = ?
                FOR UPDATE
                """,
                (dlq_id,)
            )
            
            if not dlq_entry or dlq_entry.status != 'ready_for_replay':
                return False
            
            try:
                # Create new event for replay
                new_event_id = await self.db.execute(
                    """
                    INSERT INTO payment_events (
                        payment_id,
                        event_type,
                        event_payload,
                        processed
                    )
                    VALUES (?, ?, ?, FALSE)
                    """,
                    (dlq_entry.payment_id, dlq_entry.event_type, dlq_entry.event_payload)
                )
                
                # Process immediately
                await self.process_payment_event(new_event_id)
                
                # Mark DLQ entry as replayed
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
                
                return True
                
            except Exception as e:
                # Log failure but don't crash
                await self.db.execute(
                    """
                    UPDATE payment_events_dlq
                    SET resolution_notes = CONCAT(
                        COALESCE(resolution_notes, ''),
                        '\nReplay failed: ',
                        ?
                    )
                    WHERE dlq_id = ?
                    """,
                    (str(e), dlq_id)
                )
                return False
    
    async def _handle_refund_success(self, event):
        """
        Handle successful refund with automatic restocking.
        """
        payload = json.loads(event.event_payload)
        refund_id = payload.get('refund_id')
        
        async with self.db.transaction():
            refund = await self.db.execute(
                """
                SELECT 
                    r.refund_id,
                    r.order_id,
                    r.refund_amount,
                    r.is_full_refund
                FROM refunds r
                WHERE r.refund_id = ?
                FOR UPDATE
                """,
                (refund_id,)
            )
            
            # Update payment status
            await self.db.execute(
                """
                UPDATE payments
                SET status = IF(
                    (SELECT SUM(refund_amount) FROM refunds WHERE payment_id = ?) >= amount,
                    'refunded',
                    'partially_refunded'
                )
                WHERE payment_id = ?
                """,
                (event.payment_id, event.payment_id)
            )
            
            if refund.is_full_refund:
                await self.db.execute(
                    """
                    UPDATE orders
                    SET status = 'refunded',
                        refunded_amount = total_amount
                    WHERE order_id = ?
                    """,
                    (refund.order_id,)
                )
            else:
                # Partial refund - update items and restock
                refund_items = await self.db.execute(
                    """
                    SELECT ri.order_item_id, ri.quantity, ri.refund_amount, ri.restock,
                           oi.warehouse_id, oi.product_id
                    FROM refund_items ri
                    JOIN order_items oi ON ri.order_item_id = oi.order_item_id
                    WHERE ri.refund_id = ?
                    """,
                    (refund_id,)
                )
                
                for item in refund_items:
                    # Update refunded quantities
                    await self.db.execute(
                        """
                        UPDATE order_items
                        SET refunded_quantity = refunded_quantity + ?,
                            refunded_amount = refunded_amount + ?
                        WHERE order_item_id = ?
                        """,
                        (item.quantity, item.refund_amount, item.order_item_id)
                    )
                    
                    # Restock if requested
                    if item.restock:
                        await self.db.execute(
                            """
                            UPDATE warehouse_inventory
                            SET stock_quantity = stock_quantity + ?
                            WHERE warehouse_id = ? AND product_id = ?
                            """,
                            (item.quantity, item.warehouse_id, item.product_id)
                        )
                
                # Update order
                await self.db.execute(
                    """
                    UPDATE orders
                    SET status = 'partially_refunded',
                        refunded_amount = refunded_amount + ?
                    WHERE order_id = ?
                    """,
                    (refund.refund_amount, refund.order_id)
                )
```

#### 4. Archive Service with Automated Reconciliation

```python
class OrderArchiveService:
    
    async def query_order(self, order_id: int) -> Optional[Order]:
        """
        Query order with O(1) location lookup using archive index.
        """
        location = await self._get_order_location(order_id)
        
        if location == 'active':
            order = await self.db.execute(
                """
                SELECT * FROM orders
                WHERE order_id = ? AND deleted_at IS NULL
                """,
                (order_id,)
            )
        elif location == 'archived':
            order = await self.db.execute(
                """
                SELECT * FROM orders_archive
                WHERE order_id = ?
                """,
                (order_id,)
            )
        elif location == 'cold_storage':
            storage_path = await self.db.execute(
                """
                SELECT cold_storage_path
                FROM order_archive_index
                WHERE order_id = ?
                """,
                (order_id,)
            )
            order = await self._fetch_from_cold_storage(storage_path.cold_storage_path)
        else:
            # Not indexed - check both and repair index
            order = await self._check_both_tables_and_repair(order_id)
        
        return order
    
    async def _check_both_tables_and_repair(self, order_id: int) -> Optional[Order]:
        """
        Check both tables and repair missing index entry.
        """
        # Check active first
        order = await self.db.execute(
            """
            SELECT * FROM orders
            WHERE order_id = ? AND deleted_at IS NULL
            """,
            (order_id,)
        )
        
        if order:
            # Repair index
            await self.db.execute(
                """
                INSERT INTO order_archive_index (order_id, location, last_verified_at)
                VALUES (?, 'active', NOW())
                ON DUPLICATE KEY UPDATE 
                    location = 'active',
                    last_verified_at = NOW(),
                    verification_status = 'ok'
                """,
                (order_id,)
            )
            return order
        
        # Check archive
        order = await self.db.execute(
            """
            SELECT * FROM orders_archive
            WHERE order_id = ?
            """,
            (order_id,)
        )
        
        if order:
            # Repair index
            await self.db.execute(
                """
                INSERT INTO order_archive_index (order_id, location, last_verified_at)
                VALUES (?, 'archived', NOW())
                ON DUPLICATE KEY UPDATE 
                    location = 'archived',
                    last_verified_at = NOW(),
                    verification_status = 'ok'
                """,
                (order_id,)
            )
            return order
        
        return None
    
    async def archive_old_orders(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000
    ) -> int:
        """
        Archive with index population.
        """
        terminal_states = ['delivered', 'cancelled', 'refunded', 'partially_refunded']
        total_archived = 0
        
        batch_id = await self._create_archive_batch(cutoff_date)
        
        try:
            while True:
                async with self.db.transaction():
                    orders = await self.db.execute(
                        """
                        SELECT order_id
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
                    
                    # Copy to archive tables
                    await self._copy_to_archive(order_ids)
                    
                    # Populate archive index
                    await self.db.execute(
                        """
                        INSERT INTO order_archive_index (order_id, location, archived_at, last_verified_at)
                        VALUES {}
                        ON DUPLICATE KEY UPDATE 
                            location = 'archived',
                            archived_at = NOW(),
                            last_verified_at = NOW(),
                            verification_status = 'ok'
                        """.format(','.join(['(?, "archived", NOW(), NOW())'] * len(order_ids))),
                        order_ids
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
            
            # Schedule batch verification
            await self._schedule_batch_verification(batch_id)
            
            return total_archived
            
        except Exception as e:
            await self._fail_batch(batch_id)
            raise
    
    async def reconcile_archive_index(
        self,
        reconciliation_type: str = 'spot_check',
        sample_size: int = 1000
    ) -> dict:
        """
        Reconcile archive index to detect inconsistencies.
        
        Types:
        - spot_check: Random sample of orders (default, runs nightly)
        - batch_verification: Verify specific batch after archival
        - full_scan: Complete validation (expensive, run monthly)
        """
        start_time = datetime.utcnow()
        orders_checked = 0
        discrepancies = []
        
        if reconciliation_type == 'spot_check':
            # Random sample from index
            sample = await self.db.execute(
                """
                SELECT order_id, location
                FROM order_archive_index
                ORDER BY RAND()
                LIMIT ?
                """,
                (sample_size,)
            )
            
            for entry in sample:
                actual_location = await self._verify_order_location(entry.order_id)
                if actual_location != entry.location:
                    discrepancies.append({
                        'order_id': entry.order_id,
                        'indexed_location': entry.location,
                        'actual_location': actual_location
                    })
                orders_checked += 1
        
        elif reconciliation_type == 'full_scan':
            # Check all indexed orders
            offset = 0
            batch_size = 10000
            
            while True:
                batch = await self.db.execute(
                    """
                    SELECT order_id, location
                    FROM order_archive_index
                    LIMIT ? OFFSET ?
                    """,
                    (batch_size, offset)
                )
                
                if not batch:
                    break
                
                for entry in batch:
                    actual_location = await self._verify_order_location(entry.order_id)
                    if actual_location != entry.location:
                        discrepancies.append({
                            'order_id': entry.order_id,
                            'indexed_location': entry.location,
                            'actual_location': actual_location
                        })
                    orders_checked += 1
                
                offset += batch_size
                await asyncio.sleep(0.1)  # Rate limit
        
        # Repair discrepancies
        repaired = 0
        for disc in discrepancies:
            await self.db.execute(
                """
                UPDATE order_archive_index
                SET location = ?,
                    verification_status = 'inconsistent',
                    last_verified_at = NOW()
                WHERE order_id = ?
                """,
                (disc['actual_location'], disc['order_id'])
            )
            
            # If actual location matches, mark as ok
            if disc['actual_location']:
                await self.db.execute(
                    """
                    UPDATE order_archive_index
                    SET verification_status = 'ok'
                    WHERE order_id = ?
                    """,
                    (disc['order_id'],)
                )
                repaired += 1
        
        # Log reconciliation
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        await self.db.execute(
            """
            INSERT INTO archive_reconciliation_log (
                reconciliation_type,
                orders_checked,
                discrepancies_found,
                discrepancies_resolved,
                execution_time_ms
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (reconciliation_type, orders_checked, len(discrepancies), repaired, execution_time_ms)
        )
        
        return {
            'orders_checked': orders_checked,
            'discrepancies_found': len(discrepancies),
            'discrepancies_resolved': repaired,
            'execution_time_ms': execution_time_ms
        }
    
    async def _verify_order_location(self, order_id: int) -> Optional[str]:
        """
        Verify actual location of an order.
        """
        # Check active
        active = await self.db.execute(
            """
            SELECT 1 FROM orders
            WHERE order_id = ? AND deleted_at IS NULL
            LIMIT 1
            """,
            (order_id,)
        )
        if active:
            return 'active'
        
        # Check archive
        archived = await self.db.execute(
            """
            SELECT 1 FROM orders_archive
            WHERE order_id = ?
            LIMIT 1
            """,
            (order_id,)
        )
        if archived:
            return 'archived'
        
        # Check cold storage path exists
        cold_path = await self.db.execute(
            """
            SELECT cold_storage_path
            FROM order_archive_index
            WHERE order_id = ? AND cold_storage_path IS NOT NULL
            """,
            (order_id,)
        )
        if cold_path and await self._cold_storage_exists(cold_path.cold_storage_path):
            return 'cold_storage'
        
        return None  # Missing
```

## Rationale

1. **Capacity Management with Graceful Overflow**: Warehouses get a configurable buffer (default 10%) above max capacity for peak periods. Algorithm prefers warehouses with available capacity but allows overflow to avoid hard failures. Daily counters reset automatically.

2. **Customer-Driven Allocation Strategy**: Shipping preference ('economy', 'standard', 'expedited') determines cost/speed weighting. Economy prioritizes cost (90% weight), expedited prioritizes speed (70% weight). This aligns with customer expectations and maximizes satisfaction.

3. **DLQ Operational Workflow**: Added status field ('pending_review', 'investigating', 'ready_for_replay', 'replayed', 'discarded'), assignment tracking, and priority-based routing. Critical events (money movement) get immediate alerts. Metrics dashboard tracks resolution time and queue depth.

4. **Automated Archive Reconciliation**: Nightly spot-check samples 1,000 random orders, monthly full-scan validates entire index. Discrepancies auto-repair index and flag for investigation. Reconciliation log tracks accuracy over time.

5. **Split Shipment Customer Notifications**: Shipments table includes `notification_sent` flag and `tracking_url` for email templates. Background worker finds unnotified shipments and sends tracking emails.

6. **Automatic Restocking on Refunds**: `refund_items.restock` boolean controls whether items return to warehouse inventory. Damaged/defective items set `restock=FALSE`, customer-changed-mind returns set `restock=TRUE`.

## What I Changed

1. **Capacity Enforcement Strategy**: Changed from "should we hard-fail or overflow?" to tiered approach with buffer zone. Warehouses gracefully degrade: available → buffer → overflow. Algorithm discourages overflow via 15% cost penalty but doesn't hard-fail.

2. **Allocation Strategy Configuration**: Made weights customer-configurable via `shipping_preference` enum instead of system-wide config. Stored on order for auditability. Backend derives weights automatically.

3. **DLQ Monitoring**: Added `dlq_metrics_daily` table, priority-based alerts, and operational workflow states. Operations teams see prioritized queue, not raw event dump. Dashboards show resolution SLAs.

4. **Reconciliation Automation**: Archive index includes `verification_status` and `last_verified_at`. Automated jobs (spot-check nightly, full-scan monthly) detect and repair inconsistencies without manual intervention.

5. **Geocoding Fallback**: Added `geocode_quality` enum to cache. Falls back to approximate zip centroid if high-quality geocoding fails, preventing hard errors on bad addresses.

6. **Restock Control**: Added `restock` boolean to `refund_items` so refund reasons can dictate inventory behavior. Damaged goods don't pollute good inventory.

## What I Kept

1. **Two-Phase Reservation Pattern**: Reserve with TTL → confirm on payment remains unchanged—excellent concurrency design.

2. **Payment Event Sourcing**: Complete event history with retry tracking and exponential backoff logic.

3. **Split Shipment Infrastructure**: `shipments` table and `is_split_shipment` flag for multi-warehouse orders.

4. **Version-Based Optimistic Locking**: Prevents race conditions on orders and inventory without pessimistic locks.

5. **Archive Index O(1) Lookup**: Redis + database caching eliminates double-table queries.

6. **Soft Delete Pattern**: `deleted_at` for safe recovery during archival transitions.

7. **Comprehensive Indexing**: All original indexes plus targeted additions for new query patterns.

8. **Inventory Transfer Tracking**: Warehouse-to-warehouse movement audit trail.

9. **Item-Level Refund Tracking**: Granular partial refund support with `refunded_quantity` and `refunded_amount`.

10. **Idempotency Keys**: Payment deduplication via unique idempotency keys.

## Open Questions

1. **Black Friday Capacity Overrides**: Should we support temporary capacity multipliers (e.g., 2x normal capacity for Nov 24-27) via configuration table, or rely on buffer percentage to handle spikes?

2. **DLQ Auto-Replay Criteria**: When should system automatically replay DLQ entries without human approval? E.g., "if same error resolved for 10 other entries, replay all similar entries"?

3. **Cold Storage Migration**: At what age/inactivity should archived orders move to cold storage (S3/GCS)? Archive DB still costs money. Should we auto-migrate orders >3 years old?

4. **International Warehouse Selection**: Distance calculation assumes flat-earth approximation (Haversine). For international shipments crossing oceans, should we use carrier-specific transit time APIs instead of geographic distance?

5. **Reconciliation Error Alerts**: What threshold of discrepancies triggers escalation? 0.1% error rate might be acceptable, but 1% suggests systemic issues.

## Convergence Status

**PROPOSING_FINAL** - Addressed capacity enforcement with tiered approach, DLQ operational workflow with priorities, customer-driven allocation weights, and automated reconciliation. Design is production-ready with clear operational procedures.

## PROMPT_FOR_CRITIC:

Please focus on:

1. **Capacity Overflow Handling**: Is the tiered approach (available → buffer → overflow with cost penalty) the right balance? Should we completely block overflow and return "out of capacity" errors during Black Friday instead?

2. **DLQ Auto-Replay Safety**: Under what conditions should DLQ entries automatically replay without human review? Is pattern-matching safe ("10 similar entries resolved successfully → replay all"), or should all replays require manual approval?

3. **Reconciliation Frequency**: Is nightly spot-check (1,000 samples) + monthly full-scan sufficient? Should we also reconcile immediately after each archive batch completes?

4. **Geocoding Fallback Quality**: Using approximate zip centroids when precise geocoding fails—acceptable tradeoff for resilience, or should we fail-fast and require manual address correction?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

### E-Commerce Order System - Production-Ready Schema with Operational Excellence

#### 1. Core Schema with Enhanced Operational Controls

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
    
    -- Enhanced capacity planning with time-based overrides
    base_daily_capacity INT,
    current_daily_orders INT NOT NULL DEFAULT 0,
    capacity_reset_date DATE NOT NULL,
    
    shipping_cost_base DECIMAL(8,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status_priority (status, priority),
    INDEX idx_location (latitude, longitude),
    INDEX idx_capacity_date (capacity_reset_date, current_daily_orders)
) ENGINE=InnoDB;

-- NEW: Time-based capacity overrides for peak seasons
CREATE TABLE warehouse_capacity_overrides (
    override_id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    capacity_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.0,  -- 2.0 = double capacity
    hard_capacity_limit INT,  -- Optional absolute cap
    reason VARCHAR(255),
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_warehouse_dates (warehouse_id, start_date, end_date),
    INDEX idx_date_range (start_date, end_date),
    
    CHECK (capacity_multiplier > 0),
    CHECK (end_date >= start_date)
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

CREATE TABLE geocode_cache (
    cache_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate') NOT NULL DEFAULT 'approximate',
    geocode_source VARCHAR(50) NOT NULL,  -- NEW: Track data source (Google, USPS, manual)
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_postal_country (postal_code, country),
    INDEX idx_country (country),
    INDEX idx_quality (geocode_quality),
    INDEX idx_source_quality (geocode_source, geocode_quality)  -- NEW: Audit by source
) ENGINE=InnoDB;

-- NEW: Failed geocode attempts for monitoring
CREATE TABLE geocode_failures (
    failure_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    full_address TEXT NOT NULL,
    order_id BIGINT NULL,
    failure_reason VARCHAR(255),
    fallback_used ENUM('centroid', 'none') NOT NULL,
    requires_manual_review BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    
    INDEX idx_requires_review (requires_manual_review, created_at),
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
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate'),  -- NEW: Track quality per order
    
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
    INDEX idx_geocode_quality (geocode_quality)  -- NEW: Monitor geocoding quality
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

-- NEW: Error fingerprinting for pattern-based auto-replay
CREATE TABLE payment_error_patterns (
    pattern_id INT PRIMARY KEY AUTO_INCREMENT,
    error_fingerprint VARCHAR(255) UNIQUE NOT NULL,  -- Hash of (event_type, failure_code, key error message parts)
    event_type VARCHAR(50) NOT NULL,
    failure_code VARCHAR(50),
    sample_error_message TEXT,
    
    -- Auto-replay decision
    auto_replay_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    auto_replay_confidence DECIMAL(5,2) NOT NULL DEFAULT 0.0,  -- 0-100%
    successful_replays INT NOT NULL DEFAULT 0,
    failed_replays INT NOT NULL DEFAULT 0,
    
    last_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    first_seen_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INT NOT NULL DEFAULT 1,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    INDEX idx_auto_replay (auto_replay_enabled, auto_replay_confidence),
    INDEX idx_fingerprint (error_fingerprint),
    INDEX idx_event_type (event_type)
) ENGINE=InnoDB;

CREATE TABLE payment_events_dlq (
    dlq_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    original_event_id BIGINT NOT NULL,
    payment_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_payload JSON,
    failure_reason TEXT NOT NULL,
    error_fingerprint VARCHAR(255),  -- NEW: Link to pattern for auto-replay
    retry_attempts INT NOT NULL,
    
    -- Operational workflow
    status ENUM('pending_review', 'investigating', 'auto_replay_scheduled', 'ready_for_replay', 'replayed', 'discarded') 
        NOT NULL DEFAULT 'pending_review',
    assigned_to VARCHAR(100),
    priority ENUM('low', 'medium', 'high', 'critical') NOT NULL DEFAULT 'medium',
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_at TIMESTAMP NULL,
    resolved_at TIMESTAMP NULL,
    replayed_at TIMESTAMP NULL,
    resolution_notes TEXT,
    
    FOREIGN KEY (payment_id) REFERENCES payments(payment_id),
    FOREIGN KEY (error_fingerprint) REFERENCES payment_error_patterns(error_fingerprint),
    
    INDEX idx_payment_id (payment_id),
    INDEX idx_status_priority (status, priority, created_at),
    INDEX idx_assigned_to (assigned_to, status),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_resolved (resolved_at),
    INDEX idx_error_fingerprint (error_fingerprint, status)  -- NEW: Find similar errors
) ENGINE=InnoDB;

CREATE TABLE dlq_metrics_daily (
    metric_date DATE PRIMARY KEY,
    total_entries INT NOT NULL DEFAULT 0,
    pending_review INT NOT NULL DEFAULT 0,
    investigating INT NOT NULL DEFAULT 0,
    auto_replay_scheduled INT NOT NULL DEFAULT 0,  -- NEW: Track auto-replay queue
    ready_for_replay INT NOT NULL DEFAULT 0,
    replayed_today INT NOT NULL DEFAULT 0,
    auto_replayed_today INT NOT NULL DEFAULT 0,  -- NEW: Track auto-replay success
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
    refund_reason ENUM('customer_request', 'fraud', 'duplicate', 'product_issue', 'damaged', 'other') NOT NULL,  -- NEW: Added 'damaged'
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
    INDEX idx_reason (refund_reason)  -- NEW: Analyze refund reasons
) ENGINE=InnoDB;

CREATE TABLE refund_items (
    refund_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    refund_id BIGINT NOT NULL,
    order_item_id BIGINT NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    refund_amount DECIMAL(10,2) NOT NULL,
    restock BOOLEAN NOT NULL DEFAULT TRUE,
    restock_reason ENUM('resellable', 'damaged', 'customer_kept', 'other') NOT NULL DEFAULT 'resellable',  -- NEW: Explicit reason
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (refund_id) REFERENCES refunds(refund_id) ON DELETE CASCADE,
    FOREIGN KEY (order_item_id) REFERENCES order_items(order_item_id),
    
    INDEX idx_refund_id (refund_id),
    INDEX idx_order_item_id (order_item_id),
    INDEX idx_restock (restock, created_at),
    INDEX idx_restock_reason (restock_reason)  -- NEW: Track why items not restocked
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
-- ARCHIVE SYSTEM WITH RECONCILIATION
-- ============================================

CREATE TABLE order_archive_index (
    order_id BIGINT PRIMARY KEY,
    location ENUM('active', 'archived', 'cold_storage') NOT NULL DEFAULT 'active',
    archived_at TIMESTAMP NULL,
    cold_storage_path VARCHAR(500),
    
    last_verified_at TIMESTAMP NULL,
    verification_status ENUM('ok', 'missing', 'duplicate', 'inconsistent') NOT NULL DEFAULT 'ok',
    verification_checksum VARCHAR(64),  -- NEW: SHA256 of order data for integrity
    
    INDEX idx_location (location),
    INDEX idx_archived_at (archived_at),
    INDEX idx_verification (verification_status, last_verified_at)
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
    verification_discrepancies INT NOT NULL DEFAULT 0,  -- NEW: Track issues found
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
    reconciliation_type ENUM('full_scan', 'batch_verification', 'spot_check', 'post_archive') NOT NULL,  -- NEW: Added post_archive
    orders_checked INT NOT NULL,
    discrepancies_found INT NOT NULL,
    discrepancies_resolved INT NOT NULL,
    checksum_failures INT NOT NULL DEFAULT 0,  -- NEW: Track data corruption
    execution_time_ms INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (batch_id) REFERENCES archive_batches(batch_id),
    
    INDEX idx_created_at (created_at DESC),
    INDEX idx_type_date (reconciliation_type, created_at)
) ENGINE=InnoDB;
```

#### 2. Enhanced Multi-Warehouse Service with Flexible Capacity Management

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
    capacity_utilization: Decimal  # 0.0-1.0+, can exceed 1.0 with overrides

@dataclass
class AllocationStrategy:
    """Customer-configurable allocation strategy"""
    shipping_preference: str
    prefer_single_warehouse: bool = True
    max_split_shipments: int = 2
    allow_capacity_overflow: bool = True  # NEW: Configurable per request
    
    @property
    def cost_weight(self) -> float:
        return {'economy': 0.9, 'standard': 0.7, 'expedited': 0.3}[self.shipping_preference]
    
    @property
    def speed_weight(self) -> float:
        return {'economy': 0.1, 'standard': 0.3, 'expedited': 0.7}[self.shipping_preference]

class MultiWarehouseInventoryService:
    
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
        """
        Intelligently allocate stock with configurable capacity handling.
        
        CAPACITY STRATEGY:
        - Checks for active capacity overrides (Black Friday multipliers)
        - Respects effective capacity limits (base * multiplier, or hard limit)
        - Returns capacity error ONLY if allow_capacity_overflow=False
        - Otherwise uses cost penalty to discourage but not block overflow
        """
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
                # Strict mode: only use warehouses under effective capacity
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
            
            return allocations
    
    async def _get_available_warehouses_with_capacity(
        self,
        product_id: int,
        quantity: int,
        check_date: date
    ) -> List[dict]:
        """
        Get warehouses with stock, including active capacity overrides.
        
        Capacity calculation:
        1. Check for active override on check_date
        2. If override exists:
           - Use hard_capacity_limit if set
           - Otherwise use base_daily_capacity * capacity_multiplier
        3. If no override, use base_daily_capacity
        4. Return capacity_utilization = current / effective (can exceed 1.0)
        """
        return await self.db.execute(
            """
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
                
                -- Calculate effective capacity with overrides
                COALESCE(
                    wco.hard_capacity_limit,
                    FLOOR(w.base_daily_capacity * wco.capacity_multiplier)
                ) as effective_capacity,
                
                wco.capacity_multiplier,
                wco.reason as override_reason,
                
                -- Capacity utilization ratio
                CASE 
                    WHEN COALESCE(wco.hard_capacity_limit, w.base_daily_capacity) > 0
                    THEN w.current_daily_orders / COALESCE(
                        wco.hard_capacity_limit,
                        FLOOR(w.base_daily_capacity * COALESCE(wco.capacity_multiplier, 1.0))
                    )
                    ELSE 0.0
                END as capacity_utilization
                
            FROM warehouses w
            JOIN warehouse_inventory wi 
                ON w.warehouse_id = wi.warehouse_id
            LEFT JOIN warehouse_capacity_overrides wco
                ON w.warehouse_id = wco.warehouse_id
                AND ? BETWEEN wco.start_date AND wco.end_date
            WHERE w.status = 'active'
                AND wi.product_id = ?
                AND (wi.stock_quantity - wi.reserved_quantity) > 0
            ORDER BY 
                capacity_utilization ASC,  -- Prefer warehouses with capacity headroom
                w.priority ASC
            """,
            (check_date, product_id)
        )
    
    async def _reset_warehouse_capacity_if_needed(self):
        """Reset daily capacity counters at midnight UTC."""
        today = date.today()
        
        await self.db.execute(
            """
            UPDATE warehouses
            SET current_daily_orders = 0,
                capacity_reset_date = ?
            WHERE capacity_reset_date < ?
            """,
            (today, today)
        )
    
    async def _increment_warehouse_capacity(self, warehouse_id: int):
        """Increment daily order counter."""
        await self.db.execute(
            """
            UPDATE warehouses
            SET current_daily_orders = current_daily_orders + 1
            WHERE warehouse_id = ?
            """,
            (warehouse_id,)
        )
    
    async def _score_warehouses(
        self,
        warehouses: List[dict],
        customer_coords: Tuple[float, float],
        quantity: int,
        strategy: AllocationStrategy
    ) -> List[dict]:
        """
        Score warehouses with progressive capacity penalties.
        
        Capacity penalty tiers:
        - <80% utilization: No penalty
        - 80-100%: 5% cost penalty
        - 100-110%: 10% cost penalty
        - >110%: 20% cost penalty
        """
        scored = []
        
        for wh in warehouses:
            distance = self._calculate_distance(
                (wh['latitude'], wh['longitude']),
                customer_coords
            )
            
            base_cost = wh['shipping_cost_base']
            utilization = wh['capacity_utilization']
            
            # Progressive capacity penalty
            if utilization < 0.8:
                capacity_multiplier = 1.0
            elif utilization < 1.0:
                capacity_multiplier = 1.05
            elif utilization < 1.1:
                capacity_multiplier = 1.10
            else:
                capacity_multiplier = 1.20
            
            adjusted_cost = base_cost * capacity_multiplier
            
            score = (
                strategy.cost_weight * adjusted_cost +
                strategy.speed_weight * distance
            )
            
            wh['distance_km'] = distance
            wh['score'] = score
            wh['adjusted_cost'] = adjusted_cost
            scored.append(wh)
        
        return sorted(scored, key=lambda x: x['score'])
    
    async def reallocate_on_address_change(
        self,
        order_id: int,
        new_shipping_address: Address
    ) -> dict:
        """
        Reallocate warehouse when customer changes shipping address.
        
        Returns dict with:
        - reallocated: bool
        - old_cost: Decimal
        - new_cost: Decimal
        - savings_pct: Decimal
        """
        async with self.db.transaction():
            order = await self.db.execute(
                """
                SELECT 
                    o.order_id, 
                    o.status, 
                    o.fulfillment_warehouse_id,
                    o.customer_id,
                    o.shipping_preference,
                    o.shipping_amount
                FROM orders o
                WHERE order_id = ?
                FOR UPDATE
                """,
                (order_id,)
            )
            
            if order.status not in ['confirmed', 'pending_payment', 'payment_processing']:
                return {'reallocated': False, 'reason': 'order_too_far_along'}
            
            current_reservations = await self.db.execute(
                """
                SELECT warehouse_id, product_id, quantity
                FROM inventory_reservations
                WHERE order_id = ? AND status = 'active'
                """,
                (order_id,)
            )
            
            current_cost = order.shipping_amount
            
            strategy = AllocationStrategy(
                shipping_preference=order.shipping_preference,
                prefer_single_warehouse=True,
                allow_capacity_overflow=True  # Don't fail on capacity during reallocation
            )
            
            # Simulate new allocation
            new_total_cost = Decimal(0)
            new_allocations = []
            
            for res in current_reservations:
                try:
                    new_alloc = await self._simulate_allocation(
                        product_id=res.product_id,
                        quantity=res.quantity,
                        shipping_address=new_shipping_address,
                        strategy=strategy
                    )
                    new_total_cost += sum(a.shipping_cost for a in new_alloc)
                    new_allocations.append((res, new_alloc))
                except Exception:
                    # If simulation fails, don't reallocate
                    return {'reallocated': False, 'reason': 'simulation_failed'}
            
            savings_pct = (current_cost - new_total_cost) / current_cost if current_cost > 0 else 0
            
            # Reallocate if savings > 25%
            if savings_pct > 0.25:
                # Cancel current reservations
                await self._cancel_reservations(
                    order_id, 
                    reason=f'address_change_optimization (saved {savings_pct:.1%})'
                )
                
                # Create new reservations
                for res, new_alloc in new_allocations:
                    for alloc in new_alloc:
                        await self._create_reservation(
                            warehouse_id=alloc.warehouse_id,
                            product_id=res.product_id,
                            quantity=alloc.quantity,
                            customer_id=order.customer_id,
                            order_id=order_id,
                            ttl_seconds=900
                        )
                
                # Update order
                await self.db.execute(
                    """
                    UPDATE orders
                    SET shipping_amount = ?,
                        internal_notes = CONCAT(
                            COALESCE(internal_notes, ''),
                            '\nReallocated on address change: saved ',
                            ?, '%'
                        )
                    WHERE order_id = ?
                    """,
                    (new_total_cost, f'{savings_pct * 100:.1f}', order_id)
                )
                
                return {
                    'reallocated': True,
                    'old_cost': current_cost,
                    'new_cost': new_total_cost,
                    'savings_pct': savings_pct
                }
            
            return {
                'reallocated': False,
                'reason': 'insufficient_savings',
                'savings_pct': savings_pct
            }
    
    async def _get_cached_geocode(
        self, 
        address: Address,
        order_id: Optional[int] = None
    ) -> Tuple[float, float]:
        """
        Geocode with fallback handling and failure tracking.
        
        Strategy:
        1. Check Redis cache
        2. Check database cache
        3. Attempt high-quality geocoding
        4. Fall back to centroid if needed
        5. Log failure for manual review if quality < centroid
        """
        cache_key = f"{address.postal_code}:{address.country}"
        
        cached = await self.cache.get(cache_key)
        if cached:
            return tuple(map(float, cached.split(',')))
        
        db_cached = await self.db.execute(
            """
            SELECT latitude, longitude, geocode_quality
            FROM geocode_cache
            WHERE postal_code = ? AND country = ?
            """,
            (address.postal_code, address.country)
        )
        
        if db_cached:
            await self.cache.setex(cache_key, 86400, f"{db_cached.latitude},{db_cached.longitude}")
            return (db_cached.latitude, db_cached.longitude)
        
        # Attempt geocoding
        try:
            coords, quality, source = await self.geocoding_service.geocode_with_quality(
                f"{address.city}, {address.state} {address.postal_code}, {address.country}"
            )
            
            # Store in cache
            await self.db.execute(
                """
                INSERT INTO geocode_cache (
                    postal_code, country, latitude, longitude, 
                    geocode_quality, geocode_source
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (address.postal_code, address.country, coords[0], coords[1], quality, source)
            )
            
            await self.cache.setex(cache_key, 86400, f"{coords[0]},{coords[1]}")
            return coords
            
        except GeocodingError as e:
            # Fall back to centroid
            try:
                coords, quality = await self._get_approximate_centroid(
                    address.postal_code, address.country
                )
                
                # Log failure for review
                await self.db.execute(
                    """
                    INSERT INTO geocode_failures (
                        postal_code, country, full_address, order_id,
                        failure_reason, fallback_used, requires_manual_review
                    )
                    VALUES (?, ?, ?, ?, ?, 'centroid', ?)
                    """,
                    (
                        address.postal_code, 
                        address.country,
                        f"{address.line1}, {address.city}, {address.state}",
                        order_id,
                        str(e),
                        quality == 'approximate'  # Only flag poor-quality centroids
                    )
                )
                
                # Store centroid in cache
                await self.db.execute(
                    """
                    INSERT INTO geocode_cache (
                        postal_code, country, latitude, longitude,
                        geocode_quality, geocode_source
                    )
                    VALUES (?, ?, ?, ?, ?, 'fallback_centroid')
                    """,
                    (address.postal_code, address.country, coords[0], coords[1], quality)
                )
                
                await self.cache.setex(cache_key, 86400, f"{coords[0]},{coords[1]}")
                return coords
                
            except Exception as e2:
                # Complete failure - log and fail order
                await self.db.execute(
                    """
                    INSERT INTO geocode_failures (
                        postal_code, country, full_address, order_id,
                        failure_reason, fallback_used, requires_manual_review
                    )
                    VALUES (?, ?, ?, ?, ?, 'none', TRUE)
                    """,
                    (
                        address.postal_code,
                        address.country,
                        f"{address.line1}, {address.city}, {address.state}",
                        order_id,
                        f"Geocoding failed: {e}. Centroid fallback failed: {e2}",
                    )
                )
                raise GeocodingError(f"Unable to geocode address. Order requires manual review.")
```

#### 3. Payment Service with Pattern-Based Auto-Replay

```python
from typing import Optional
import asyncio
import hashlib
from datetime import datetime, timedelta
from enum import Enum

class PaymentService:
    
    MAX_RETRY_ATTEMPTS = 5
    BASE_RETRY_DELAY = 30
    AUTO_REPLAY_THRESHOLD = 10  # Successful replays needed to enable auto-replay
    AUTO_REPLAY_MIN_CONFIDENCE = 85.0  # Minimum success rate (%)
    
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
        """
        Handle failed event with intelligent DLQ routing and pattern learning.
        """
        retry_count = event.retry_count + 1
        
        if retry_count >= self.MAX_RETRY_ATTEMPTS:
            # Generate error fingerprint
            fingerprint = self._generate_error_fingerprint(
                event.event_type,
                event.failure_code,
                str(error)
            )
            
            # Update pattern statistics
            await self._update_error_pattern(fingerprint, event.event_type, event.failure_code, str(error))
            
            # Check if auto-replay is enabled for this pattern
            pattern = await self.db.execute(
                """
                SELECT auto_replay_enabled, auto_replay_confidence
                FROM payment_error_patterns
                WHERE error_fingerprint = ?
                """,
                (fingerprint,)
            )
            
            priority = self._calculate_dlq_priority(event)
            
            # Determine initial status
            if pattern and pattern.auto_replay_enabled:
                initial_status = 'auto_replay_scheduled'
            else:
                initial_status = 'pending_review'
            
            dlq_id = await self.db.execute(
                """
                INSERT INTO payment_events_dlq (
                    original_event_id,
                    payment_id,
                    event_type,
                    event_payload,
                    failure_reason,
                    error_fingerprint,
                    retry_attempts,
                    status,
                    priority
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event.event_id, event.payment_id, event.event_type,
                 event.event_payload, str(error), fingerprint, retry_count,
                 initial_status, priority.value)
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
            if pattern and pattern.auto_replay_enabled:
                await self._schedule_auto_replay(dlq_id, fingerprint, pattern.auto_replay_confidence)
            elif priority in ['high', 'critical']:
                await self.alerting_service.send_alert(
                    severity=priority,
                    message=f"Payment event {event.event_id} moved to DLQ",
                    details={
                        'event_id': event.event_id,
                        'payment_id': event.payment_id,
                        'dlq_id': dlq_id,
                        'amount': event.amount,
                        'event_type': event.event_type,
                        'error_fingerprint': fingerprint
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
    
    def _generate_error_fingerprint(
        self,
        event_type: str,
        failure_code: Optional[str],
        error_message: str
    ) -> str:
        """
        Generate fingerprint for error pattern matching.
        
        Fingerprint includes:
        - Event type
        - Failure code (if available)
        - Normalized error message (remove IDs, timestamps, etc.)
        """
        # Normalize error message
        import re
        normalized = re.sub(r'\d+', 'N', error_message)  # Replace numbers
        normalized = re.sub(r'[a-f0-9]{32,}', 'HASH', normalized)  # Replace hashes
        normalized = normalized.lower()[:200]  # Take first 200 chars
        
        fingerprint_input = f"{event_type}:{failure_code or 'none'}:{normalized}"
        return hashlib.sha256(fingerprint_input.encode()).hexdigest()[:16]
    
    async def _update_error_pattern(
        self,
        fingerprint: str,
        event_type: str,
        failure_code: Optional[str],
        error_message: str
    ):
        """
        Update error pattern statistics for auto-replay decisions.
        """
        await self.db.execute(
            """
            INSERT INTO payment_error_patterns (
                error_fingerprint,
                event_type,
                failure_code,
                sample_error_message,
                occurrence_count,
                last_seen_at
            )
            VALUES (?, ?, ?, ?, 1, NOW())
            ON DUPLICATE KEY UPDATE
                occurrence_count = occurrence_count + 1,
                last_seen_at = NOW()
            """,
            (fingerprint, event_type, failure_code, error_message[:500])
        )
    
    async def _schedule_auto_replay(
        self,
        dlq_id: int,
        fingerprint: str,
        confidence: Decimal
    ):
        """
        Schedule automatic replay for known-good error patterns.
        
        Replays after 5 minutes to allow transient issues to resolve.
        """
        await self.task_queue.enqueue(
            task='auto_replay_dlq_entry',
            args={'dlq_id': dlq_id, 'fingerprint': fingerprint},
            execute_at=datetime.utcnow() + timedelta(minutes=5)
        )
        
        await self.logger.info(
            f"Auto-replay scheduled for DLQ {dlq_id} "
            f"(pattern confidence: {confidence}%)"
        )
    
    async def auto_replay_dlq_entry(self, dlq_id: int, fingerprint: str) -> bool:
        """
        Automatically replay DLQ entry based on learned pattern.
        """
        async with self.db.transaction():
            dlq_entry = await self.db.execute(
                """
                SELECT 
                    dlq_id, original_event_id, payment_id,
                    event_type, event_payload, status
                FROM payment_events_dlq
                WHERE dlq_id = ?
                FOR UPDATE
                """,
                (dlq_id,)
            )
            
            if not dlq_entry or dlq_entry.status != 'auto_replay_scheduled':
                return False
            
            try:
                # Create new event
                new_event_id = await self.db.execute(
                    """
                    INSERT INTO payment_events (
                        payment_id, event_type, event_payload, processed
                    )
                    VALUES (?, ?, ?, FALSE)
                    """,
                    (dlq_entry.payment_id, dlq_entry.event_type, dlq_entry.event_payload)
                )
                
                # Process immediately
                await self.process_payment_event(new_event_id)
                
                # Mark as replayed
                await self.db.execute(
                    """
                    UPDATE payment_events_dlq
                    SET status = 'replayed',
                        replayed_at = NOW(),
                        resolution_notes = 'Automatically replayed via pattern matching'
                    WHERE dlq_id = ?
                    """,
                    (dlq_id,)
                )
                
                # Update pattern success
                await self.db.execute(
                    """
                    UPDATE payment_error_patterns
                    SET successful_replays = successful_replays + 1,
                        auto_replay_confidence = (successful_replays + 1) * 100.0 / 
                            (successful_replays + failed_replays + 1)
                    WHERE error_fingerprint = ?
                    """,
                    (fingerprint,)
                )
                
                return True
                
            except Exception as e:
                # Mark as failed and update pattern
                await self.db.execute(
                    """
                    UPDATE payment_events_dlq
                    SET status = 'pending_review',
                        resolution_notes = CONCAT(
                            'Auto-replay failed: ', ?
                        )
                    WHERE dlq_id = ?
                    """,
                    (str(e), dlq_id)
                )
                
                await self.db.execute(
                    """
                    UPDATE payment_error_patterns
                    SET failed_replays = failed_replays + 1,
                        auto_replay_confidence = successful_replays * 100.0 / 
                            (successful_replays + failed_replays + 1),
                        auto_replay_enabled = CASE 
                            WHEN auto_replay_confidence < ? THEN FALSE
                            ELSE auto_replay_enabled
                        END
                    WHERE error_fingerprint = ?
                    """,
                    (self.AUTO_REPLAY_MIN_CONFIDENCE, fingerprint)
                )
                
                return False
    
    async def enable_auto_replay_for_pattern(
        self,
        fingerprint: str,
        operator: str
    ) -> bool:
        """
        Manually enable auto-replay after ops team validates pattern.
        """
        pattern = await self.db.execute(
            """
            SELECT successful_replays, failed_replays, occurrence_count
            FROM payment_error_patterns
            WHERE error_fingerprint = ?
            """,
            (fingerprint,)
        )
        
        if not pattern:
            return False
        
        # Require at least 5 successful manual replays
        if pattern.successful_replays < 5:
            raise ValueError(
                f"Pattern needs {5 - pattern.successful_replays} more "
                f"successful replays before auto-replay can be enabled"
            )
        
        confidence = pattern.successful_replays * 100.0 / (
            pattern.successful_replays + pattern.failed_replays
        )
        
        if confidence < self.AUTO_REPLAY_MIN_CONFIDENCE:
            raise ValueError(
                f"Pattern confidence ({confidence:.1f}%) below threshold "
                f"({self.AUTO_REPLAY_MIN_CONFIDENCE}%)"
            )
        
        await self.db.execute(
            """
            UPDATE payment_error_patterns
            SET auto_replay_enabled = TRUE,
                auto_replay_confidence = ?
            WHERE error_fingerprint = ?
            """,
            (confidence, fingerprint)
        )
        
        await self.logger.info(
            f"Auto-replay enabled for pattern {fingerprint} by {operator} "
            f"(confidence: {confidence:.1f}%)"
        )
        
        return True
    
    def _calculate_dlq_priority(self, event) -> str:
        """Assign DLQ priority based on event type and amount."""
        critical_events = ['capture_succeeded', 'refund_succeeded']
        high_events = ['authorization_succeeded']
        medium_events = ['capture_failed', 'refund_failed', 'capture_requested']
        
        if event.event_type in critical_events:
            return 'critical'
        elif event.event_type in high_events:
            return 'high'
        elif event.event_type in medium_events:
            return 'medium'
        else:
            return 'low'
    
    async def replay_dlq_entry(self, dlq_id: int, operator: str) -> dict:
        """
        Manual replay of DLQ entry by operations team.
        
        Returns replay result and updates pattern learning.
        """
        async with self.db.transaction():
            dlq_entry = await self.db.execute(
                """
                SELECT 
                    dlq_id, original_event_id, payment_id,
                    event_type, event_payload, status, error_fingerprint
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
                
                # Update pattern learning
                if dlq_entry.error_fingerprint:
                    await self.db.execute(
                        """
                        UPDATE payment_error_patterns
                        SET successful_replays = successful_replays + 1,
                            auto_replay_confidence = (successful_replays + 1) * 100.0 / 
                                (successful_replays + failed_replays + 1)
                        WHERE error_fingerprint = ?
                        """,
                        (dlq_entry.error_fingerprint,)
                    )
                    
                    # Check if pattern qualifies for auto-replay
                    pattern = await self.db.execute(
                        """
                        SELECT successful_replays, auto_replay_confidence
                        FROM payment_error_patterns
                        WHERE error_fingerprint = ?
                        """,
                        (dlq_entry.error_fingerprint,)
                    )
                    
                    if (pattern.successful_replays >= self.AUTO_REPLAY_THRESHOLD and
                        pattern.auto_replay_confidence >= self.AUTO_REPLAY_MIN_CONFIDENCE):
                        return {
                            'success': True,
                            'pattern_ready_for_auto_replay': True,
                            'fingerprint': dlq_entry.error_fingerprint
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
                
                # Update pattern failure
                if dlq_entry.error_fingerprint:
                    await self.db.execute(
                        """
                        UPDATE payment_error_patterns
                        SET failed_replays = failed_replays + 1,
                            auto_replay_confidence = successful_replays * 100.0 / 
                                (successful_replays + failed_replays + 1)
                        WHERE error_fingerprint = ?
                        """,
                        (dlq_entry.error_fingerprint,)
                    )
                
                return {'success': False, 'error': str(e)}
    
    async def _handle_refund_success(self, event):
        """Handle successful refund with automatic restocking."""
        payload = json.loads(event.event_payload)
        refund_id = payload.get('refund_id')
        
        async with self.db.transaction():
            refund = await self.db.execute(
                """
                SELECT r.refund_id, r.order_id, r.refund_amount, r.is_full_refund
                FROM refunds r
                WHERE r.refund_id = ?
                FOR UPDATE
                """,
                (refund_id,)
            )
            
            await self.db.execute(
                """
                UPDATE payments
                SET status = IF(
                    (SELECT SUM(refund_amount) FROM refunds WHERE payment_id = ?) >= amount,
                    'refunded',
                    'partially_refunded'
                )
                WHERE payment_id = ?
                """,
                (event.payment_id, event.payment_id)
            )
            
            if refund.is_full_refund:
                await self.db.execute(
                    """
                    UPDATE orders
                    SET status = 'refunded', refunded_amount = total_amount
                    WHERE order_id = ?
                    """,
                    (refund.order_id,)
                )
            else:
                refund_items = await self.db.execute(
                    """
                    SELECT ri.order_item_id, ri.quantity, ri.refund_amount, 
                           ri.restock, ri.restock_reason,
                           oi.warehouse_id, oi.product_id
                    FROM refund_items ri
                    JOIN order_items oi ON ri.order_item_id = oi.order_item_id
                    WHERE ri.refund_id = ?
                    """,
                    (refund_id,)
                )
                
                for item in refund_items:
                    await self.db.execute(
                        """
                        UPDATE order_items
                        SET refunded_quantity = refunded_quantity + ?,
                            refunded_amount = refunded_amount + ?
                        WHERE order_item_id = ?
                        """,
                        (item.quantity, item.refund_amount, item.order_item_id)
                    )
                    
                    # Restock only if marked as resellable
                    if item.restock and item.restock_reason == 'resellable':
                        await self.db.execute(
                            """
                            UPDATE warehouse_inventory
                            SET stock_quantity = stock_quantity + ?
                            WHERE warehouse_id = ? AND product_id = ?
                            """,
                            (item.quantity, item.warehouse_id, item.product_id)
                        )
                
                await self.db.execute(
                    """
                    UPDATE orders
                    SET status = 'partially_refunded',
                        refunded_amount = refunded_amount + ?
                    WHERE order_id = ?
                    """,
                    (refund.refund_amount, refund.order_id)
                )
```

#### 4. Archive Service with Post-Archive Verification

```python
class OrderArchiveService:
    
    async def query_order(self, order_id: int) -> Optional[Order]:
        """Query order with O(1) location lookup."""
        location = await self._get_order_location(order_id)
        
        if location == 'active':
            order = await self.db.execute(
                "SELECT * FROM orders WHERE order_id = ? AND deleted_at IS NULL",
                (order_id,)
            )
        elif location == 'archived':
            order = await self.db.execute(
                "SELECT * FROM orders_archive WHERE order_id = ?",
                (order_id,)
            )
        elif location == 'cold_storage':
            storage_path = await self.db.execute(
                "SELECT cold_storage_path FROM order_archive_index WHERE order_id = ?",
                (order_id,)
            )
            order = await self._fetch_from_cold_storage(storage_path.cold_storage_path)
        else:
            order = await self._check_both_tables_and_repair(order_id)
        
        return order
    
    async def archive_old_orders(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000
    ) -> int:
        """
        Archive with immediate post-archive verification.
        """
        terminal_states = ['delivered', 'cancelled', 'refunded', 'partially_refunded']
        total_archived = 0
        
        batch_id = await self._create_archive_batch(cutoff_date)
        
        try:
            while True:
                async with self.db.transaction():
                    orders = await self.db.execute(
                        """
                        SELECT order_id
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
                    
                    # Copy to archive with checksum
                    await self._copy_to_archive_with_checksum(order_ids)
                    
                    # Populate index
                    await self.db.execute(
                        """
                        INSERT INTO order_archive_index (
                            order_id, location, archived_at, 
                            last_verified_at, verification_checksum
                        )
                        VALUES {}
                        ON DUPLICATE KEY UPDATE 
                            location = 'archived',
                            archived_at = NOW(),
                            last_verified_at = NOW(),
                            verification_status = 'ok'
                        """.format(','.join(['(?, "archived", NOW(), NOW(), ?)'] * len(order_ids))),
                        # Flatten list of (order_id, checksum) tuples
                        [val for order_id in order_ids 
                         for val in (order_id, await self._calculate_order_checksum(order_id))]
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
            
            # Immediate post-archive verification
            await self.reconcile_archive_batch(batch_id)
            
            return total_archived
            
        except Exception as e:
            await self._fail_batch(batch_id)
            raise
    
    async def reconcile_archive_batch(self, batch_id: int) -> dict:
        """
        Verify specific archive batch immediately after completion.
        
        Checks:
        1. All orders exist in archive table
        2. All orders removed from active table
        3. Checksums match
        """
        start_time = datetime.utcnow()
        
        batch = await self.db.execute(
            "SELECT orders_archived FROM archive_batches WHERE batch_id = ?",
            (batch_id,)
        )
        
        order_ids = await self.db.execute(
            """
            SELECT order_id, verification_checksum
            FROM order_archive_index
            WHERE archived_at >= (
                SELECT created_at FROM archive_batches WHERE batch_id = ?
            )
            AND archived_at <= (
                SELECT completed_at FROM archive_batches WHERE batch_id = ?
            )
            """,
            (batch_id, batch_id)
        )
        
        discrepancies = 0
        checksum_failures = 0
        
        for entry in order_ids:
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
            
            # Verify checksum
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
                batch_id,
                reconciliation_type,
                orders_checked,
                discrepancies_found,
                discrepancies_resolved,
                checksum_failures,
                execution_time_ms
            )
            VALUES (?, 'post_archive', ?, ?, 0, ?, ?)
            """,
            (batch_id, len(order_ids), discrepancies, checksum_failures, execution_time_ms)
        )
        
        # Update batch status
        if discrepancies == 0:
            await self.db.execute(
                """
                UPDATE archive_batches
                SET status = 'verified',
                    verified_at = NOW(),
                    verification_discrepancies = 0
                WHERE batch_id = ?
                """,
                (batch_id,)
            )
        else:
            await self.db.execute(
                """
                UPDATE archive_batches
                SET verification_discrepancies = ?
                WHERE batch_id = ?
                """,
                (discrepancies, batch_id)
            )
            
            # Alert if significant issues
            if discrepancies > len(order_ids) * 0.01:  # >1% error rate
                await self.alerting_service.send_alert(
                    severity='high',
                    message=f"Archive batch {batch_id} verification failed",
                    details={
                        'batch_id': batch_id,
                        'discrepancies': discrepancies,
                        'checksum_failures': checksum_failures,
                        'total_orders': len(order_ids)
                    }
                )
        
        return {
            'orders_checked': len(order_ids),
            'discrepancies_found': discrepancies,
            'checksum_failures': checksum_failures,
            'execution_time_ms': execution_time_ms
        }
    
    async def reconcile_archive_index(
        self,
        reconciliation_type: str = 'spot_check',
        sample_size: int = 1000
    ) -> dict:
        """
        Reconcile archive index to detect inconsistencies.
        """
        start_time = datetime.utcnow()
        orders_checked = 0
        discrepancies = []
        checksum_failures = 0
        
        if reconciliation_type == 'spot_check':
            sample = await self.db.execute(
                """
                SELECT order_id, location, verification_checksum
                FROM order_archive_index
                ORDER BY RAND()
                LIMIT ?
                """,
                (sample_size,)
            )
            
            for entry in sample:
                actual_location = await self._verify_order_location(entry.order_id)
                
                if actual_location != entry.location:
                    discrepancies.append({
                        'order_id': entry.order_id,
                        'indexed_location': entry.location,
                        'actual_location': actual_location,
                        'issue': 'location_mismatch'
                    })
                elif entry.verification_checksum:
                    # Verify checksum
                    if entry.location == 'archived':
                        actual_checksum = await self._calculate_archived_order_checksum(entry.order_id)
                    elif entry.location == 'active':
                        actual_checksum = await self._calculate_order_checksum(entry.order_id)
                    else:
                        actual_checksum = None
                    
                    if actual_checksum and actual_checksum != entry.verification_checksum:
                        discrepancies.append({
                            'order_id': entry.order_id,
                            'issue': 'checksum_mismatch'
                        })
                        checksum_failures += 1
                
                orders_checked += 1
        
        elif reconciliation_type == 'full_scan':
            offset = 0
            batch_size = 10000
            
            while True:
                batch = await self.db.execute(
                    """
                    SELECT order_id, location, verification_checksum
                    FROM order_archive_index
                    LIMIT ? OFFSET ?
                    """,
                    (batch_size, offset)
                )
                
                if not batch:
                    break
                
                for entry in batch:
                    actual_location = await self._verify_order_location(entry.order_id)
                    
                    if actual_location != entry.location:
                        discrepancies.append({
                            'order_id': entry.order_id,
                            'indexed_location': entry.location,
                            'actual_location': actual_location,
                            'issue': 'location_mismatch'
                        })
                    
                    orders_checked += 1
                
                offset += batch_size
                await asyncio.sleep(0.1)
        
        # Repair discrepancies
        repaired = 0
        for disc in discrepancies:
            if disc.get('actual_location'):
                await self.db.execute(
                    """
                    UPDATE order_archive_index
                    SET location = ?,
                        verification_status = 'ok',
                        last_verified_at = NOW()
                    WHERE order_id = ?
                    """,
                    (disc['actual_location'], disc['order_id'])
                )
                repaired += 1
            else:
                await self.db.execute(
                    """
                    UPDATE order_archive_index
                    SET verification_status = ?,
                        last_verified_at = NOW()
                    WHERE order_id = ?
                    """,
                    (disc['issue'], disc['order_id'])
                )
        
        execution_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        await self.db.execute(
            """
            INSERT INTO archive_reconciliation_log (
                reconciliation_type, orders_checked, discrepancies_found,
                discrepancies_resolved, checksum_failures, execution_time_ms
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (reconciliation_type, orders_checked, len(discrepancies),
             repaired, checksum_failures, execution_time_ms)
        )
        
        return {
            'orders_checked': orders_checked,
            'discrepancies_found': len(discrepancies),
            'discrepancies_resolved': repaired,
            'checksum_failures': checksum_failures,
            'execution_time_ms': execution_time_ms
        }
    
    async def _calculate_order_checksum(self, order_id: int) -> str:
        """Calculate SHA256 checksum of order data for integrity verification."""
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
        
        # Serialize order data deterministically
        import json
        serialized = json.dumps(dict(order_data), sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    async def _calculate_archived_order_checksum(self, order_id: int) -> str:
        """Calculate checksum from archived table."""
        order_data = await self.db.execute(
            """
            SELECT o.*, 
                   GROUP_CONCAT(oi.order_item_id ORDER BY oi.order_item_id) as items
            FROM orders_archive o
            LEFT JOIN order_items_archive oi ON o.order_id = oi.order_id
            WHERE o.order_id = ?
            GROUP BY o.order_id
            """,
            (order_id,)
        )
        
        import json
        serialized = json.dumps(dict(order_data), sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()
```

## What I Improved

1. **Capacity Management System**: Replaced static buffer approach with time-based capacity overrides table. Allows configuring Black Friday as "2x capacity from Nov 24-27" or setting hard limits. More flexible than fixed buffer percentages and makes seasonal planning explicit in the database.

2. **Configurable Overflow Policy**: Made capacity overflow behavior request-specific via `AllocationStrategy.allow_capacity_overflow`. Critical orders can disable overflow (fail-fast), while standard orders allow it. Removes one-size-fits-all approach.

3. **Pattern-Based DLQ Auto-Replay**: Added error fingerprinting and learning system. System tracks success/failure rate per error pattern. After 10 successful manual replays with >85% confidence, pattern qualifies for auto-replay. Ops team can enable/disable per pattern. Safer than threshold-based auto-replay.

4. **Geocoding Failure Tracking**: Added `geocode_failures` table with `requires_manual_review` flag. Low-quality fallbacks (approximate centroids) log failure but don't block order. Complete failures require manual address correction. Orders store `geocode_quality` for audit.

5. **Post-Archive Verification**: Added immediate reconciliation after each archive batch completes (in addition to spot-checks). Uses SHA256 checksums to detect data corruption. Alerts if >1% error rate in batch.

6. **Restock Reason Tracking**: Added `restock_reason` enum ('resellable', 'damaged', 'customer_kept') to `refund_items`. Only 'resellable' items return to inventory. Provides inventory quality controls and refund analytics.

7. **Capacity Utilization Scoring**: Changed from discrete tiers (available/buffer/overflow) to continuous utilization ratio (0.0-1.0+). Progressive penalties discourage high utilization without hard cutoffs.

8. **DLQ Status Refinement**: Added 'auto_replay_scheduled' status to distinguish human-queued from machine-queued replays. Improves ops team workload visibility.

## What I Kept

1. **Two-Phase Reservation Pattern**: TTL-based reservations with confirm-on-payment
2. **Payment Event Sourcing**: Complete audit trail with retry logic
3. **Optimistic Locking**: Version-based concurrency control
4. **Archive Index**: O(1) location lookup pattern
5. **Soft Deletes**: Safe archival transitions with `deleted_at`
6. **Split Shipment Infrastructure**: Multi-warehouse order support
7. **Comprehensive Indexing**: All query patterns covered
8. **Idempotency Keys**: Payment deduplication
9. **Inventory Transfer Tracking**: Warehouse-to-warehouse movement log
10. **DLQ Priority System**: Risk-based operational triage

## Remaining Concerns

1. **Error Pattern False Positives**: What if two different root causes produce the same fingerprint? Auto-replay could mask real issues. Should we add time-windowing (pattern only valid for 7 days)?

2. **Capacity Override Conflicts**: If overlapping overrides exist (Nov 20-30 and Nov 24-27), which takes precedence? Need conflict resolution rules or validation constraints.

3. **Checksum Performance Impact**: SHA256 on every archived order adds overhead. For high-volume archives (millions of orders), should we sample checksums (e.g., 10% of orders) instead of 100%?

4. **Geocode Centroid Data Source**: Who maintains the centroid fallback data? USPS? Do we pre-populate all US zip codes, or fetch on-demand? What about international addresses?

5. **Archive Verification SLA**: Post-archive verification runs synchronously, delaying batch completion. Should we make it async (fire-and-forget) to avoid blocking archival throughput?

6. **Auto-Replay Timing**: Currently replays after 5 minutes. Is this enough time for transient gateway issues to resolve? Too long for customers waiting on order confirmation?

## PROMPT_FOR_ARCHITECT:

Focus your review on:

1. **Capacity Override Precedence**: With overlapping date ranges, should last-created win? Highest multiplier? Smallest range? Or should we prevent overlaps entirely via CHECK constraint?

2. **Error Fingerprint Stability**: Current fingerprint uses normalized error message (numbers→N, hashes→HASH). Will this catch typos like "Connection timed out" vs "Connection timeout"? Should we use fuzzy matching or manual pattern grouping?

3. **Checksum Sampling Strategy**: For archives >100k orders/day, full checksumming could take hours. Would random 10% sampling catch corruption reliably? Or should we only checksum high-value orders (>$1000)?

4. **Geocoding Failure UX**: When geocoding fails completely and order requires manual review, what happens to the customer? Order stuck in "pending"? Email requesting address correction? Auto-cancel after 24 hours?

5. **Capacity Utilization Alerting**: At what utilization threshold should ops teams receive warnings? 80%? 90%? Should alerts be per-warehouse or system-wide?

**Convergence Signal:** ITERATING

---

## Round 4

### 🔵 Agent A

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

## Rationale

1. **Priority-Based Capacity Override Resolution**: Explicit `priority` field in `warehouse_capacity_overrides` with deterministic conflict resolution (lowest priority number wins, ties broken by most recent). This replaces ambiguous "what if overlaps?" with clear operator control. Ops team can set Black Friday override as priority=1 to ensure it takes precedence.

2. **Manual Error Classification**: Replaced automatic fingerprinting with manually-curated `payment_error_classes` table. Ops team defines patterns with SQL LIKE wildcards and keyword arrays. More stable than text normalization (catches "timeout"/"timed out" via keywords). Requires human validation before auto-replay, preventing false positive replay storms.

3. **Tiered Archive Verification**: Three-tier system balances cost vs integrity:
   - High-value orders (>$1000): Always verified with checksum (100% coverage)
   - Standard orders: 10% random sample with checksum
   - Configurable 'full' mode for compliance audits
   
   Rationale: Checksum computation is ~5ms per order. For 100k orders/day, full checksumming = 500 seconds (8 minutes) synchronous overhead. Sampling reduces to 50 seconds while catching systematic corruption. High-value orders get extra protection.

4. **Geocoding Failure UX Workflow**: Added explicit `address_review` order status and customer notification system. When geocoding fails:
   - Order transitions to `address_review`
   - Customer receives email with verification link
   - 48-hour deadline before auto-cancel
   - Ops dashboard shows orders needing review
   
   This prevents "order stuck forever" scenario while maintaining order flow visibility.

5. **Capacity Alerting System**: Added `capacity_alerts` table with configurable thresholds (80% warning, 95% critical). Alerts auto-resolve when utilization drops. System-wide view via warehouse_id grouping. Ops team can tune thresholds per warehouse or globally.

6. **Geocode Three-Tier Lookup**: Pre-populated `geocode_reference` table for common postal codes (US zip centroids from USPS data). Reduces API calls by ~70% for repeat addresses. Lookup chain: Redis (hot) → DB cache (warm) → Reference table (pre-populated) → API (cold) → Fallback centroid.

7. **Stored Computed Column for Confidence**: `auto_replay_confidence` as GENERATED ALWAYS AS stored column ensures consistency and eliminates calculation bugs. Updates automatically when `successful_replays` or `failed_replays` change.

## What I Changed

1. **Capacity Override Conflict Resolution**: Added `priority` field and ROW_NUMBER() window function to deterministically select highest-priority override when ranges overlap. Prevents ambiguous behavior.

2. **Error Classification Model**: Replaced automatic fingerprinting with manual pattern definition. Changed from `error_fingerprint` hash to structured `payment_error_classes` with LIKE patterns and keyword matching. More reliable for auto-replay decisions.

3. **Archive Verification Strategy**: Split from "always checksum everything" to three configurable strategies (full/sampled/high_value_only). Added `verification_tier` to orders and `sample_percentage` tracking to batches.

4. **Geocoding Failure Handling**: Added customer notification workflow with new `address_review` status, `customer_notified` flag, and `resolution_status` enum. Order doesn't silently fail—customer gets 48 hours to correct.

5. **Capacity Monitoring**: Added dedicated `capacity_alerts` table with real-time threshold checking and auto-resolution. Moved from ad-hoc alerting to structured ops workflow.

6. **Geocode Cache Structure**: Split into `geocode_reference` (pre-populated, permanent) and `geocode_cache` (runtime, LRU-evictable). Added `hit_count` and `last_accessed_at` for cache effectiveness metrics.

7. **DLQ Status Granularity**: Added `pending_classification` status to distinguish unclassified errors from classified-but-pending-review. Improves ops team workload visibility.

## What I Kept

1. **Two-Phase Reservation Pattern**: TTL-based reservations with confirm-on-payment
2. **Payment Event Sourcing**: Complete audit trail with retry logic
3. **Optimistic Locking**: Version-based concurrency control on critical tables
4. **Archive Index Pattern**: O(1) location lookup via dedicated index table
5. **Soft Deletes**: Safe archival transitions with `deleted_at` timestamp
6. **Split Shipment Infrastructure**: Multi-warehouse order fulfillment support
7. **Comprehensive Indexing**: All query patterns covered with appropriate indexes
8. **Idempotency Keys**: Payment gateway deduplication
9. **Inventory Transfer Tracking**: Warehouse-to-warehouse movement audit log
10. **DLQ Priority System**: Risk-based operational triage (low/medium/high/critical)

## Open Questions

1. **Geocode Reference Table Maintenance**: Who populates `geocode_reference`? Do we bulk-import USPS zip centroid data on deployment? How often do we refresh (quarterly? annually?)? International coverage strategy?

2. **Error Class Overfitting**: If ops team creates too many narrow error classes (e.g., "stripe_timeout_tuesday_morning"), we risk missing patterns. Should we enforce minimum occurrence count (e.g., 50 instances) before allowing class creation?

3. **Archive Verification Sampling Bias**: Random 10% sampling could miss localized corruption (e.g., corruption only in orders 50000-51000). Should we use stratified sampling (sample across order_id ranges) instead of pure random?

4. **Capacity Override Expiry**: Old overrides accumulate forever. Should we auto-archive overrides >90 days past `end_date`? Or add `archived` boolean flag to prevent query bloat?

5. **Customer Address Correction Rate**: If <10% of customers respond to verification emails, we'll have high auto-cancel rates. Should we add phone/SMS verification as escalation before auto-cancel?

## Convergence Status

**ITERATING** - Design needs review on:
- Geocode reference table data sourcing strategy
- Error classification workflow (ops team training, tooling)
- Archive sampling statistical validity
- Capacity override housekeeping

## PROMPT_FOR_CRITIC:

Focus your critique on:

1. **Geocode Reference Table Strategy**: Should `geocode_reference` be pre-populated on deployment (requires USPS data license), or populated lazily on first API call? How do we handle international addresses (OpenStreetMap bulk data? Per-country strategy?)?

2. **Error Classification Tooling**: Manually defining SQL LIKE patterns in `payment_error_classes` is error-prone. Should we build admin UI with pattern testing (show matching DLQ entries before saving)? Or provide SQL function `test_error_class(class_id, dlq_id) RETURNS BOOLEAN`?

3. **Archive Sampling Statistical Power**: Is 10% random sampling sufficient to detect corruption with 95% confidence? Should we calculate sample size based on batch size (e.g., n = 384 for 100k orders, 95% confidence, 5% margin)?

4. **Capacity Override UX**: Overlapping overrides with priority might confuse operators ("which override is active?"). Should we add validation that warns/blocks overlaps, forcing ops to explicitly merge ranges?

5. **Customer Address Verification Deadline**: 48 hours might be too aggressive for international customers or weekend orders. Should deadline be business-days aware? Or configurable per order based on shipping preference (expedited = 24h, standard = 72h)?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

### E-Commerce Order System - Production Schema with Enhanced Operational Clarity

#### 1. Core Schema with Resolved Operational Controls

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
    
    base_daily_capacity INT,
    current_daily_orders INT NOT NULL DEFAULT 0,
    capacity_reset_date DATE NOT NULL,
    
    shipping_cost_base DECIMAL(8,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_status_priority (status, priority),
    INDEX idx_location (latitude, longitude),
    INDEX idx_capacity_date (capacity_reset_date, current_daily_orders)
) ENGINE=InnoDB;

-- Simplified capacity overrides with explicit non-overlapping enforcement
CREATE TABLE warehouse_capacity_overrides (
    override_id INT PRIMARY KEY AUTO_INCREMENT,
    warehouse_id INT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    capacity_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.0,
    hard_capacity_limit INT,
    reason VARCHAR(255),
    created_by VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
    
    INDEX idx_warehouse_dates (warehouse_id, start_date, end_date),
    INDEX idx_date_range (start_date, end_date),
    
    CHECK (capacity_multiplier > 0),
    CHECK (end_date >= start_date),
    CHECK (hard_capacity_limit IS NULL OR hard_capacity_limit > 0),
    
    -- Enforce non-overlapping ranges per warehouse via trigger
    UNIQUE KEY uk_warehouse_date_range (warehouse_id, start_date, end_date)
) ENGINE=InnoDB;

-- Overlap validation trigger
DELIMITER $$
CREATE TRIGGER validate_capacity_override_overlap
BEFORE INSERT ON warehouse_capacity_overrides
FOR EACH ROW
BEGIN
    DECLARE overlap_count INT;
    
    SELECT COUNT(*) INTO overlap_count
    FROM warehouse_capacity_overrides
    WHERE warehouse_id = NEW.warehouse_id
      AND override_id != COALESCE(NEW.override_id, -1)
      AND NOT (NEW.end_date < start_date OR NEW.start_date > end_date);
    
    IF overlap_count > 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Capacity override overlaps with existing range. Please merge or adjust dates.';
    END IF;
END$$
DELIMITER ;

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

-- ============================================
-- GEOCODING SYSTEM
-- ============================================

-- Strategy: Lazy population with bulk import support
CREATE TABLE geocode_reference (
    reference_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate') NOT NULL,
    data_source ENUM('usps', 'openstreetmap', 'google', 'manual', 'bulk_import') NOT NULL,
    admin_area_1 VARCHAR(100),  -- State/Province for better matching
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uk_postal_country (postal_code, country),
    INDEX idx_country_admin (country, admin_area_1),
    INDEX idx_quality_source (geocode_quality, data_source)
) ENGINE=InnoDB;

-- Bulk import staging table
CREATE TABLE geocode_import_staging (
    import_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    admin_area_1 VARCHAR(100),
    data_source VARCHAR(50) NOT NULL,
    import_batch_id VARCHAR(100) NOT NULL,
    imported_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    processed BOOLEAN NOT NULL DEFAULT FALSE,
    
    INDEX idx_batch_processed (import_batch_id, processed),
    INDEX idx_postal_country (postal_code, country)
) ENGINE=InnoDB;

-- Runtime cache with TTL and adaptive eviction
CREATE TABLE geocode_cache (
    cache_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    latitude DECIMAL(10,8) NOT NULL,
    longitude DECIMAL(11,8) NOT NULL,
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate') NOT NULL,
    geocode_source ENUM('api', 'reference_table', 'fallback') NOT NULL,
    hit_count INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_accessed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ttl_hours INT NOT NULL DEFAULT 168,  -- 7 days default
    
    UNIQUE KEY uk_postal_country (postal_code, country),
    INDEX idx_country (country),
    INDEX idx_quality (geocode_quality),
    INDEX idx_eviction (last_accessed_at, hit_count),  -- LRU + frequency
    INDEX idx_ttl_expired (created_at, ttl_hours)  -- TTL-based cleanup
) ENGINE=InnoDB;

-- Failed geocoding with configurable retry and business-hours awareness
CREATE TABLE geocode_failures (
    failure_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    postal_code VARCHAR(20) NOT NULL,
    country CHAR(2) NOT NULL,
    full_address TEXT NOT NULL,
    order_id BIGINT NULL,
    failure_reason VARCHAR(255),
    fallback_strategy ENUM('centroid', 'customer_corrected', 'none') NOT NULL,
    customer_notified BOOLEAN NOT NULL DEFAULT FALSE,
    resolution_status ENUM('pending', 'customer_contacted', 'corrected', 'cancelled') NOT NULL DEFAULT 'pending',
    notification_deadline TIMESTAMP NULL,  -- Business-hours aware deadline
    resolved_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    
    INDEX idx_resolution_status (resolution_status, notification_deadline),
    INDEX idx_postal_country (postal_code, country),
    INDEX idx_created_at (created_at DESC),
    INDEX idx_deadline (notification_deadline)
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
        'address_review',
        'confirmed', 
        'processing',
        'partially_shipped',
        'shipped', 
        'delivered', 
        'cancelled', 
        'refunded',
        'partially_refunded'
    ) NOT NULL DEFAULT 'cart',
    
    subtotal_amount DECIMAL(12,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    shipping_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    discount_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    total_amount DECIMAL(12,2) NOT NULL,
    refunded_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    currency_code CHAR(3) NOT NULL DEFAULT 'USD',
    
    fulfillment_warehouse_id INT NULL,
    is_split_shipment BOOLEAN NOT NULL DEFAULT FALSE,
    shipping_preference ENUM('standard', 'expedited', 'economy') NOT NULL DEFAULT 'standard',
    
    -- Shipping information
    shipping_address_line1 VARCHAR(255),
    shipping_address_line2 VARCHAR(255),
    shipping_city VARCHAR(100),
    shipping_state VARCHAR(100),
    shipping_postal_code VARCHAR(20),
    shipping_country CHAR(2),
    shipping_latitude DECIMAL(10,8),
    shipping_longitude DECIMAL(11,8),
    geocode_quality ENUM('rooftop', 'range_interpolated', 'centroid', 'approximate'),
    geocode_requires_review BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Billing information
    billing_address_line1 VARCHAR(255),
    billing_address_line2 VARCHAR(255),
    billing_city VARCHAR(100),
    billing_state VARCHAR(100),
    billing_postal_code VARCHAR(20),
    billing_country CHAR(2),
    
    customer_notes TEXT,
    internal_notes TEXT,
    
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    payment_confirmed_at TIMESTAMP NULL,
    shipped_at TIMESTAMP NULL,
    delivered_at TIMESTAMP NULL,
    cancelled_at TIMESTAMP NULL,
    
    version INT NOT NULL DEFAULT 1,
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
    INDEX idx_geocode_review (geocode_requires_review, status)
) ENGINE=InnoDB ROW_FORMAT=COMPRESSED;

CREATE TABLE order_items (
    order_item_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    warehouse_id INT NOT NULL,
    
    product_sku VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    subtotal DECIMAL(10,2) NOT NULL,
    
    refunded_quantity INT NOT NULL DEFAULT 0,
    refunded_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
    
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
-- PAYMENT SYSTEM
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

-- Simplified error classification with admin UI support via stored function
CREATE TABLE payment_error_classes (
    class_id INT PRIMARY KEY AUTO_INCREMENT,
    class_name VARCHAR(100) UNIQUE NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    
    gateway_pattern VARCHAR(100),
    failure_code_pattern VARCHAR(100),
    message_keywords JSON,
    
    auto_replay_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    auto_replay_delay_seconds INT NOT NULL DEFAULT 300,
    min_confidence_threshold DECIMAL(5,2) NOT NULL DEFAULT 85.0,
    
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
    INDEX idx_event_type (event_type),
    INDEX idx_confidence (auto_replay_confidence DESC)
) ENGINE=InnoDB;

-- Admin UI helper function
DELIMITER $$
CREATE FUNCTION test_error_class(
    p_class_id INT,
    p_gateway VARCHAR(100),
    p_failure_code VARCHAR(50),
    p_error_message TEXT
) RETURNS BOOLEAN
READS SQL DATA
BEGIN
    DECLARE v_gateway_pattern VARCHAR(100);
    DECLARE v_failure_code_pattern VARCHAR(100);
    DECLARE v_message_keywords JSON;
    DECLARE v_matches BOOLEAN DEFAULT TRUE;
    
    SELECT gateway_pattern, failure_code_pattern, message_keywords
    INTO v_gateway_pattern, v_failure_code_pattern, v_message_keywords
    FROM payment_error_classes
    WHERE class_id = p_class_id;
    
    -- Test gateway pattern
    IF v_gateway_pattern IS NOT NULL THEN
        SET v_matches = v_matches AND (p_gateway REGEXP REPLACE(v_gateway_pattern, '%', '.*'));
    END IF;
    
    -- Test failure code pattern
    IF v_failure_code_pattern IS NOT NULL AND p_failure_code IS NOT NULL THEN
        SET v_matches = v_matches AND (p_failure_code REGEXP REPLACE(v_failure_code_pattern, '%', '.*'));
    END IF;
    
    -- Test message keywords (simplified check)
    IF v_message_keywords IS NOT NULL THEN
        -- In production, iterate through JSON array
        SET v_matches = v_matches AND (JSON_LENGTH(v_message_keywords) > 0);
    END IF;
    
    RETURN v_matches;
END$$
DELIMITER ;

CREATE TABLE payment_events_dlq (
    dlq_id BIGINT PRIMARY KEY AUTO_INCREMENT,
    original_event_id BIGINT NOT NULL,
    payment_id BIGINT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_payload JSON,
    failure_reason TEXT NOT NULL,
    error_class_id INT NULL,
    retry_attempts INT NOT NULL,
    
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
-- ARCHIVE SYSTEM WITH STATISTICAL SAMPLING
-- ============================================

CREATE TABLE order_archive_index (
    order_id BIGINT PRIMARY KEY,
    location ENUM('active', 'archived', 'cold_storage') NOT NULL DEFAULT 'active',
    archived_at TIMESTAMP NULL,
    cold_storage_path VARCHAR(500),
    
    verification_tier ENUM('standard', 'high_value') NOT NULL DEFAULT 'standard',
    order_total DECIMAL(12,2),
    
    last_verified_at TIMESTAMP NULL,
    verification_status ENUM('ok', 'missing', 'duplicate', 'inconsistent') NOT NULL DEFAULT 'ok',
    verification_checksum VARCHAR(64),
    
    INDEX idx_location (location),
    INDEX idx_archived_at (archived_at),
    INDEX idx_verification (verification_status, last_verified_at),
    INDEX idx_verification_tier (verification_tier)
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
    
    verification_strategy ENUM('sampled', 'high_value_only', 'full') NOT NULL DEFAULT 'sampled',
    target_sample_size INT,  -- Statistically calculated sample size
    actual_sample_size INT,
    high_value_orders_verified INT NOT NULL DEFAULT 0,
    confidence_level DECIMAL(5,2) DEFAULT 95.0,
    margin_of_error DECIMAL(5,2) DEFAULT 5.0,
    
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
    capacity_utilization DECIMAL(5,2) NOT NULL,
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

#### 2. Enhanced Geocoding Service with Business-Hours Deadline

```python
from typing import List, Optional, Tuple
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime, timedelta
from enum import Enum

@dataclass
class DeadlineConfig:
    shipping_preference: str
    deadline_hours: int
    use_business_hours: bool = True
    
    @classmethod
    def from_preference(cls, preference: str) -> 'DeadlineConfig':
        configs = {
            'expedited': cls('expedited', 24, False),  # Calendar hours
            'standard': cls('standard', 72, True),     # Business hours
            'economy': cls('economy', 96, True)        # Business hours
        }
        return configs.get(preference, configs['standard'])

class GeocodingService:
    
    def __init__(self, db, redis, config):
        self.db = db
        self.redis = redis
        self.config = config
        self.business_hours_start = 9  # 9 AM
        self.business_hours_end = 17   # 5 PM
        self.business_days = set([0, 1, 2, 3, 4])  # Mon-Fri
    
    async def calculate_notification_deadline(
        self,
        order_created_at: datetime,
        shipping_preference: str,
        customer_timezone: str = 'UTC'
    ) -> datetime:
        """
        Calculate business-hours-aware deadline for customer response.
        
        Example:
        - Order created: Friday 4 PM
        - Standard shipping: 72 business hours
        - Deadline: Wednesday 4 PM (skips weekend)
        """
        deadline_config = DeadlineConfig.from_preference(shipping_preference)
        
        if not deadline_config.use_business_hours:
            # Simple calendar hours for expedited
            return order_created_at + timedelta(hours=deadline_config.deadline_hours)
        
        # Business hours calculation
        current = order_created_at
        hours_remaining = deadline_config.deadline_hours
        
        while hours_remaining > 0:
            # Skip to next business day if weekend
            while current.weekday() not in self.business_days:
                current += timedelta(days=1)
                current = current.replace(
                    hour=self.business_hours_start,
                    minute=0,
                    second=0
                )
            
            # Calculate hours left in current business day
            current_hour = current.hour + current.minute / 60.0
            
            if current_hour < self.business_hours_start:
                current = current.replace(
                    hour=self.business_hours_start,
                    minute=0,
                    second=0
                )
                current_hour = self.business_hours_start
            
            hours_in_day = self.business_hours_end - current_hour
            
            if hours_remaining <= hours_in_day:
                # Deadline falls within today
                current += timedelta(hours=hours_remaining)
                hours_remaining = 0
            else:
                # Move to next business day
                hours_remaining -= hours_in_day
                current += timedelta(days=1)
                current = current.replace(
                    hour=self.business_hours_start,
                    minute=0,
                    second=0
                )
        
        return current
    
    async def bulk_import_geocode_data(
        self,
        data_source: str,
        import_batch_id: str,
        records: List[dict]
    ) -> dict:
        """
        Bulk import geocode reference data from USPS/OSM datasets.
        
        Usage:
        - Initial deployment: Import USPS zip centroids (33,000 US zips)
        - Quarterly refresh: Re-import updated centroids
        - International: Import OSM postal code centroids by country
        
        Example record:
        {
            'postal_code': '94103',
            'country': 'US',
            'latitude': 37.7749,
            'longitude': -122.4194,
            'admin_area_1': 'CA'
        }
        """
        # Stage records
        staging_records = []
        for record in records:
            staging_records.append({
                'postal_code': record['postal_code'],
                'country': record['country'],
                'latitude': record['latitude'],
                'longitude': record['longitude'],
                'admin_area_1': record.get('admin_area_1'),
                'data_source': data_source,
                'import_batch_id': import_batch_id
            })
        
        # Bulk insert to staging
        await self.db.execute_many(
            """
            INSERT INTO geocode_import_staging (
                postal_code, country, latitude, longitude,
                admin_area_1, data_source, import_batch_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (r['postal_code'], r['country'], r['latitude'], r['longitude'],
                 r['admin_area_1'], r['data_source'], r['import_batch_id'])
                for r in staging_records
            ]
        )
        
        # Process staged records (upsert to reference table)
        result = await self.db.execute(
            """
            INSERT INTO geocode_reference (
                postal_code, country, latitude, longitude,
                geocode_quality, data_source, admin_area_1
            )
            SELECT 
                postal_code, country, latitude, longitude,
                'centroid', data_source, admin_area_1
            FROM geocode_import_staging
            WHERE import_batch_id = ?
              AND processed = FALSE
            ON DUPLICATE KEY UPDATE
                latitude = VALUES(latitude),
                longitude = VALUES(longitude),
                data_source = VALUES(data_source),
                admin_area_1 = VALUES(admin_area_1),
                last_updated = NOW()
            """,
            (import_batch_id,)
        )
        
        # Mark staged records as processed
        await self.db.execute(
            """
            UPDATE geocode_import_staging
            SET processed = TRUE
            WHERE import_batch_id = ?
            """,
            (import_batch_id,)
        )
        
        return {
            'batch_id': import_batch_id,
            'records_imported': result.rowcount,
            'data_source': data_source
        }
    
    async def get_cached_geocode(
        self,
        address: 'Address',
        order_id: Optional[int] = None,
        shipping_preference: str = 'standard'
    ) -> Tuple[float, float, str]:
        """
        Three-tier geocode lookup with business-aware failure handling.
        """
        cache_key = f"{address.postal_code}:{address.country}"
        
        # Tier 1: Redis (hot)
        cached = await self.redis.get(cache_key)
        if cached:
            lat, lon, quality = cached.split(',')
            return (float(lat), float(lon), quality)
        
        # Tier 2: Database cache
        db_cached = await self.db.execute(
            """
            UPDATE geocode_cache
            SET hit_count = hit_count + 1,
                last_accessed_at = NOW()
            WHERE postal_code = ? AND country = ?
              AND TIMESTAMPDIFF(HOUR, created_at, NOW()) < ttl_hours
            RETURNING latitude, longitude, geocode_quality
            """,
            (address.postal_code, address.country)
        )
        
        if db_cached:
            await self.redis.setex(
                cache_key,
                86400,
                f"{db_cached.latitude},{db_cached.longitude},{db_cached.geocode_quality}"
            )
            return (db_cached.latitude, db_cached.longitude, db_cached.geocode_quality)
        
        # Tier 3: Reference table
        reference = await self.db.execute(
            """
            SELECT latitude, longitude, geocode_quality
            FROM geocode_reference
            WHERE postal_code = ? AND country = ?
            """,
            (address.postal_code, address.country)
        )
        
        if reference:
            await self._promote_to_cache(
                address.postal_code, address.country,
                reference.latitude, reference.longitude,
                reference.geocode_quality, 'reference_table'
            )
            return (reference.latitude, reference.longitude, reference.geocode_quality)
        
        # Tier 4: External API
        try:
            coords, quality = await self._call_geocoding_api(address)
            
            await self._promote_to_cache(
                address.postal_code, address.country,
                coords[0], coords[1], quality, 'api'
            )
            
            return (coords[0], coords[1], quality)
            
        except GeocodingError as e:
            # Tier 5: Fallback with customer notification
            await self._handle_geocode_failure(
                address, order_id, str(e), shipping_preference
            )
            
            country_centroid = await self._get_country_centroid(address.country)
            return (country_centroid[0], country_centroid[1], 'approximate')
    
    async def _handle_geocode_failure(
        self,
        address: 'Address',
        order_id: Optional[int],
        error_message: str,
        shipping_preference: str
    ):
        """Handle geocoding failure with business-hours deadline."""
        order_created_at = datetime.utcnow()
        
        if order_id:
            order_data = await self.db.execute(
                "SELECT created_at FROM orders WHERE order_id = ?",
                (order_id,)
            )
            if order_data:
                order_created_at = order_data.created_at
        
        deadline = await self.calculate_notification_deadline(
            order_created_at,
            shipping_preference
        )
        
        failure_id = await self.db.execute(
            """
            INSERT INTO geocode_failures (
                postal_code, country, full_address, order_id,
                failure_reason, fallback_strategy, resolution_status,
                notification_deadline
            )
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                address.postal_code,
                address.country,
                f"{address.line1}, {address.city}, {address.state}",
                order_id,
                error_message,
                'centroid',
                deadline
            )
        )
        
        if order_id:
            await self.db.execute(
                """
                UPDATE orders
                SET status = 'address_review',
                    geocode_requires_review = TRUE,
                    geocode_quality = 'approximate'
                WHERE order_id = ?
                """,
                (order_id,)
            )
            
            await self.task_queue.enqueue(
                task='notify_customer_address_verification',
                args={
                    'order_id': order_id,
                    'failure_id': failure_id,
                    'deadline': deadline.isoformat()
                }
            )
```

#### 3. Archive Service with Statistical Sampling

```python
import math
from typing import Optional
from decimal import Decimal

class OrderArchiveService:
    
    HIGH_VALUE_THRESHOLD = Decimal('1000.00')
    
    def calculate_sample_size(
        self,
        population_size: int,
        confidence_level: float = 0.95,
        margin_of_error: float = 0.05,
        expected_error_rate: float = 0.01
    ) -> int:
        """
        Calculate statistically valid sample size using Cochran's formula.
        
        Formula: n = (Z^2 * p * (1-p)) / e^2
        Where:
        - Z = Z-score for confidence level (1.96 for 95%)
        - p = expected error rate (0.01 = 1%)
        - e = margin of error (0.05 = 5%)
        
        With finite population correction:
        n_adjusted = n / (1 + (n-1)/N)
        
        Example:
        - Population: 100,000 orders
        - Confidence: 95% (Z=1.96)
        - Margin: 5%
        - Expected error: 1%
        
        Result: n ≈ 384 samples needed
        """
        # Z-scores for common confidence levels
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence_level, 1.96)
        
        # Cochran's formula
        n = (z ** 2 * expected_error_rate * (1 - expected_error_rate)) / (margin_of_error ** 2)
        
        # Finite population correction
        if population_size < 50000:  # Only apply for smaller populations
            n = n / (1 + (n - 1) / population_size)
        
        return max(int(math.ceil(n)), 30)  # Minimum 30 samples
    
    async def archive_old_orders(
        self,
        cutoff_date: datetime,
        batch_size: int = 1000,
        verification_strategy: str = 'sampled',
        confidence_level: float = 0.95,
        margin_of_error: float = 0.05
    ) -> int:
        """Archive with statistical sampling."""
        terminal_states = ['delivered', 'cancelled', 'refunded', 'partially_refunded']
        total_archived = 0
        
        # Count total orders to archive
        total_count = await self.db.execute(
            """
            SELECT COUNT(*) as cnt
            FROM orders
            WHERE created_at < ?
              AND status IN (?, ?, ?, ?)
              AND deleted_at IS NULL
            """,
            (cutoff_date, *terminal_states)
        )
        
        # Calculate sample size for statistical verification
        target_sample_size = None
        if verification_strategy == 'sampled':
            target_sample_size = self.calculate_sample_size(
                total_count.cnt,
                confidence_level,
                margin_of_error
            )
        
        batch_id = await self._create_archive_batch(
            cutoff_date,
            verification_strategy,
            target_sample_size,
            confidence_level,
            margin_of_error
        )
        
        try:
            high_value_count = 0
            standard_orders = []
            
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
                    
                    # Categorize orders
                    for order in orders:
                        is_high_value = order.total_amount >= self.HIGH_VALUE_THRESHOLD
                        verification_tier = 'high_value' if is_high_value else 'standard'
                        
                        if is_high_value:
                            high_value_count += 1
                        else:
                            standard_orders.append(order.order_id)
                        
                        checksum = None
                        if verification_strategy == 'full' or is_high_value:
                            checksum = await self._calculate_order_checksum(order.order_id)
                        
                        await self.db.execute(
                            """
                            INSERT INTO order_archive_index (
                                order_id, location, archived_at,
                                verification_tier, order_total,
                                verification_checksum, verification_status
                            )
                            VALUES (?, 'archived', NOW(), ?, ?, ?, 'ok')
                            """,
                            (order.order_id, verification_tier, order.total_amount, checksum)
                        )
                    
                    # Soft delete
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
            
            # Statistical sampling for standard orders
            if verification_strategy == 'sampled' and standard_orders:
                import random
                sample_size = min(target_sample_size - high_value_count, len(standard_orders))
                sampled_orders = random.sample(standard_orders, sample_size)
                
                # Calculate checksums for sampled orders
                for order_id in sampled_orders:
                    checksum = await self._calculate_order_checksum(order_id)
                    await self.db.execute(
                        """
                        UPDATE order_archive_index
                        SET verification_checksum = ?,
                            last_verified_at = NOW()
                        WHERE order_id = ?
                        """,
                        (checksum, order_id)
                    )
            
            await self._complete_batch(batch_id, total_archived)
            
            # Verify batch
            await self.verify_archive_batch(batch_id, verification_strategy)
            
            return total_archived
            
        except Exception as e:
            await self._fail_batch(batch_id)
            raise
    
    async def _create_archive_batch(
        self,
        cutoff_date: datetime,
        strategy: str,
        target_sample_size: Optional[int],
        confidence_level: float,
        margin_of_error: float
    ) -> int:
        """Create batch with sampling parameters."""
        return await self.db.execute(
            """
            INSERT INTO archive_batches (
                archive_date, orders_archived, oldest_order_date,
                newest_order_date, status, verification_strategy,
                target_sample_size, confidence_level, margin_of_error
            )
            VALUES (CURDATE(), 0, ?, ?, 'in_progress', ?, ?, ?, ?)
            """,
            (cutoff_date, cutoff_date, strategy, target_sample_size,
             confidence_level, margin_of_error)
        )
```

## What I Improved

1. **Capacity Override Simplified with Hard Constraints**: Removed priority-based overlap resolution in favor of **non-overlapping enforcement via trigger**. Operators cannot create overlapping ranges—they must explicitly merge or adjust dates. This eliminates "which override wins?" confusion and prevents accidental conflicts. The trigger provides immediate feedback at insert time rather than silent winner selection.

2. **Error Classification Admin Tooling**: Added `test_error_class()` stored function for pattern validation. Ops can test patterns against real DLQ entries before saving: `SELECT test_error_class(5, 'stripe', 'timeout', 'connection timed out') → TRUE`. This catches regex mistakes and keyword typos before they cause misclassification.

3. **Statistical Sample Size Calculation**: Replaced arbitrary 10% sampling with **Cochran's formula** for statistically valid sample sizes. For 100k orders with 95% confidence and 5% margin of error, only ~384 samples needed (0.4% of population). This reduces checksum overhead by 96% while maintaining detection power. Formula adjusts automatically for smaller batches.

4. **Business-Hours Deadline Calculation**: Added `calculate_notification_deadline()` method that skips weekends and non-business hours for standard/economy shipping. Example: Order placed Friday 4 PM → 72 business-hour deadline = Wednesday 4 PM (skips weekend). Expedited orders use calendar hours (no weekend skip). Prevents unfair weekend deadlines.

5. **Geocode Bulk Import Infrastructure**: Added `geocode_import_staging` table and `bulk_import_geocode_data()` method for deployment-time data loading. Supports USPS zip centroids (33k records), OpenStreetMap postal codes (international), or custom datasets. Import is idempotent (upsert) and trackable via `import_batch_id`.

6. **Cache TTL and Adaptive Eviction**: Added `ttl_hours` column to `geocode_cache` with separate index for expired entry cleanup. High-hit entries can have extended TTL (adaptive), while one-off lookups expire faster. Prevents cache bloat from rare addresses.

7. **Archive Verification Tier Tracking**: Split sample tracking into `target_sample_size` (statistically calculated) and `actual_sample_size` (what was verified). Added `confidence_level` and `margin_of_error` to batch metadata for audit trail. Dashboard can show "This batch verified 384 of 100k orders (95% confidence, ±5% error)".

## What I Kept

1. **Two-Phase Reservation with TTL**: Prevents overselling during checkout
2. **Payment Event Sourcing**: Complete audit trail with DLQ workflow
3. **Optimistic Locking**: Version-based concurrency on critical tables
4. **Manual Error Classification Model**: Human-curated patterns for auto-replay
5. **Tiered Archive Verification**: High-value orders always verified
6. **Capacity Alerting System**: Real-time threshold monitoring
7. **Three-Tier Geocode Lookup**: Redis → DB cache → Reference → API → Fallback
8. **Address Review Workflow**: Customer notification on geocode failure
9. **Soft Deletes**: Safe archival with `deleted_at` timestamp
10. **Comprehensive Indexing**: All query patterns covered

## Remaining Concerns

1. **Geocode Reference Stale Data**: Pre-populated USPS centroids become stale as postal codes change (new subdivisions, boundary adjustments). How often do we refresh? Quarterly bulk refresh risks downtime during import. Should we version reference data and blue-green swap tables?

2. **Trigger Performance on High-Volume Inserts**: The `validate_capacity_override_overlap` trigger runs on every insert, requiring a full table scan of overlapping date ranges. For warehouses with 100+ historical overrides, this could become slow. Should we add a status flag (active/expired) to limit scan scope?

3. **Sample Stratification for Temporal Corruption**: Random sampling might miss corruption clustered by time (e.g., archival bug on specific date range). Should we use stratified sampling (divide population into time buckets, sample from each bucket proportionally)?

4. **Geocode Cache Eviction Strategy**: LRU + TTL can conflict (high-hit entry with expired TTL vs low-hit entry within TTL). Should we use LRU-K (track K most recent accesses) or LFU (frequency-based) instead of simple LRU?

5. **Business Hours Timezone Handling**: Customer timezone affects deadline fairness (US customer ordering at 11 PM PST has less real time than EST customer). Should deadlines be calculated in customer's local timezone rather than UTC?

## Convergence Status

**ITERATING** - Design needs review on:
- Capacity override trigger performance implications
- Statistical sampling temporal stratification
- Geocode reference data lifecycle management
- Cache eviction strategy optimization

## PROMPT_FOR_ARCHITECT:

Focus your next iteration on:

1. **Capacity Override Trigger Performance**: Is a full table scan acceptable for overlap checking? Should we add a `status ENUM('active', 'expired')` column and partial index on `WHERE status='active'` to limit scan scope? Or move validation to application layer with advisory lock?

2. **Geocode Reference Data Versioning**: How do we handle reference table updates without downtime? Blue-green table swap (`geocode_reference_v2` → atomic rename)? Or versioned rows with `effective_date` range and application-layer version selection?

3. **Archive Sampling Stratification**: Should we stratify samples by order creation date (e.g., divide 90-day archive window into 9 deciles, sample proportionally from each)? This catches temporal clustering of corruption at cost of complexity. Is random sampling sufficient given checksums detect any corruption?

4. **Error Classification False Positives**: What happens if an error class pattern is too broad and auto-replays incorrect DLQ entries? Should we add a "confidence cooldown"—disable auto-replay for 24 hours after first failure and require manual review?

5. **Business Hours Configuration Granularity**: Should business hours be warehouse-specific (fulfillment center hours) or customer timezone-specific? Current design uses system-wide 9-5 Mon-Fri, but international expansion needs per-region configuration.

**Convergence Signal:** ITERATING

---

