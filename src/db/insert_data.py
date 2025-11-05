from src.db.connector import MongoDBClient


def init_mongodb(products: list):
    try:
        db_client = MongoDBClient()
        for product in products:
            try:
                db_client.insert_product(product)
                print(f"Inserted: {product['product']}")
            except ValueError as e:
                print(f"Skipping {product['product']}: {str(e)}")
    except Exception as e:
        print(f"Error initializing MongoDB: {str(e)}")


if __name__ == "__main__":
    example_data = [
        {
            "product_id": "1",
            "product": "iPhone 15 Pro Max",
            "storage": "256GB",
            "color": "Titan tự nhiên",
            "price": 27990000,
            "quantity": 3
        },
        {
            "product_id": "2",
            "product": "iPhone 15 Pro",
            "storage": "1TB",
            "color": "Gold Rose",
            "price": 26990000,
            "quantity": 1
        },
        {
            "product_id": "3",
            "product": "iPhone 12 Pro",
            "storage": "512GB",
            "color": "Graphite",
            "price": 24990000,
            "quantity": 5
        },
        {
            "product_id": "4",
            "product": "Samsung Galaxy S23 Ultra",
            "storage": "512GB",
            "color": "Phantom Black",
            "price": 32990000,
            "quantity": 2
        },
        {
            "product_id": "5",
            "product": "MacBook Pro 16 inch M1 Pro",
            "storage": "512GB",
            "color": "Silver",
            "price": 49990000,
            "quantity": 1
        },
        {
            "product_id": "6",
            "product": "Dell XPS 13",
            "storage": "256GB",
            "color": "Black",
            "price": 24990000,
            "quantity": 4
        }
    ]
    init_mongodb(example_data)