import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super_secure_feedme_key'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'feedme_v2.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    allergies = db.Column(db.String(200), default="")

class FoodItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    category = db.Column(db.String(50))
    ingredients = db.Column(db.String(200))
    price = db.Column(db.Float)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    items_json = db.Column(db.Text)
    total_price = db.Column(db.Float)

# --- LOGIC HELPERS ---

def get_safety_status(item_ingredients, user_allergies):
    if not user_allergies: return "SAFE"
    allergies = [a.strip().lower() for a in user_allergies.split(',')]
    ingredients = [i.strip().lower() for i in item_ingredients.split(',')]
    for a in allergies:
        if a in ingredients: return "DANGER"
    return "SAFE"

# --- ROUTES ---

@app.route('/')
def home():
    if 'user_id' not in session: 
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Debugging check: Does the user exist in the DB?
    if user is None:
        print("DEBUG: User not found in database for session ID", session['user_id'])
        session.pop('user_id', None) # Clear invalid session
        return redirect(url_for('login'))

    menu = FoodItem.query.all()
    
    for item in menu:
        # Debugging check: Does the item exist?
        if item is None:
            continue
            
        if item.ingredients:
            item.status = get_safety_status(item.ingredients, user.allergies)
        else:
            item.status = "SAFE"
            
    return render_template('dashboard.html', user=user, menu=menu)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form['password'], method='pbkdf2:sha256')
        new_user = User(
            username=request.form['username'], 
            password=hashed_pw,
            allergies=request.form['allergies']
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password, request.form['password']):
            session['user_id'] = user.id
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/build/<int:item_id>', methods=['GET', 'POST'])
def build_order(item_id):
    item = FoodItem.query.get_or_404(item_id)
    ingredients = [i.strip() for i in item.ingredients.split(',')]
    if request.method == 'POST':
        selected = request.form.getlist('ingredients')
        removed_count = len(ingredients) - len(selected)
        final_price = item.price - (removed_count * 0.50)
        new_order = Order(
            user_id=session['user_id'],
            items_json=f"{item.name} ({', '.join(selected)})",
            total_price=final_price
        )
        db.session.add(new_order)
        db.session.commit()
        return redirect(url_for('view_orders'))
    return render_template('build.html', item=item, ingredients=ingredients)

@app.route('/orders')
def view_orders():
    user_orders = Order.query.filter_by(user_id=session['user_id']).all()
    return render_template('orders.html', orders=user_orders)

@app.route('/edit_order/<int:order_id>', methods=['GET', 'POST'])
def edit_order(order_id):
    order = Order.query.get_or_404(order_id)
    item_name = order.items_json.split(' (')[0]
    item = FoodItem.query.filter_by(name=item_name).first()
    
    if not item:
        return "Original item not found.", 404

    all_ingredients = [i.strip() for i in item.ingredients.split(',')]
    try:
        current_selected = order.items_json.split('(')[1].replace(')', '').split(', ')
    except:
        current_selected = all_ingredients

    if request.method == 'POST':
        selected = request.form.getlist('ingreds')
        removed_count = len(all_ingredients) - len(selected)
        final_price = item.price - (removed_count * 0.50)
        order.items_json = f"{item.name} ({', '.join(selected)})"
        order.total_price = final_price
        db.session.commit()
        return redirect(url_for('view_orders'))
        
    return render_template('edit_order.html', order=order, all_ingredients=all_ingredients, current_selected=current_selected)

@app.route('/delete_order/<int:id>')
def delete_order(id):
    order = Order.query.get_or_404(id)
    db.session.delete(order)
    db.session.commit()
    return redirect(url_for('view_orders'))

# THE START BLOCK - MUST BE AT THE VERY BOTTOM
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not FoodItem.query.first():
            # Diverse Menu Options
            menu_data = [
                ("Big Mac", "Main", "Beef, Lettuce, Cheese, Pickles, Bun", 5.99),
                ("Quarter Pounder", "Main", "Beef, Onion, Pickle, Ketchup, Mustard, Bun", 6.49),
                ("McChicken", "Main", "Chicken, Lettuce, Mayo, Bun", 4.99),
                ("Filet-O-Fish", "Main", "Fish, Cheese, Tartar Sauce, Bun", 4.50),
                ("Double Cheeseburger", "Main", "Beef, Cheese, Ketchup, Bun", 3.50),
                ("Spicy Chicken Sandwich", "Main", "Chicken, Lettuce, Mayo, Bun", 5.29),
                ("McRib", "Main", "Pork, BBQ Sauce, Onion, Pickle", 5.99),
                ("Egg McMuffin", "Main", "Egg, Ham, Cheese, English Muffin", 3.99),
                ("Sausage Burrito", "Main", "Egg, Sausage, Tortilla", 3.50),
                ("Bacon Egg Biscuit", "Main", "Bacon, Egg, Cheese, Biscuit", 4.25),
                ("French Fries", "Side", "Potato, Salt, Oil", 2.99),
                ("Chicken McNuggets", "Side", "Chicken, Flour, Oil", 5.49),
                ("Apple Pie", "Side", "Apple, Flour, Sugar, Cinnamon", 1.50),
                ("Onion Rings", "Side", "Onion, Flour, Oil", 3.00),
                ("Hash Browns", "Side", "Potato, Oil, Salt", 1.99),
                ("Fruit Yogurt Parfait", "Side", "Yogurt, Granola, Berries", 2.99),
                ("Side Salad", "Side", "Lettuce, Tomato, Cucumber", 2.00),
                ("Mozzarella Sticks", "Side", "Cheese, Flour, Oil", 3.50),
                ("Coca-Cola", "Drink", "Sugar, Water, Carbonation", 1.99),
                ("Iced Coffee", "Drink", "Coffee, Milk, Sugar", 2.49),
                ("Strawberry Shake", "Drink", "Milk, Strawberry, Sugar", 2.99),
                ("Chocolate Milk", "Drink", "Milk, Cocoa, Sugar", 1.75),
                ("Hot Chocolate", "Drink", "Milk, Cocoa, Sugar", 2.25),
                ("Orange Juice", "Drink", "Oranges", 2.50),
                ("Vanilla Cone", "Side", "Milk, Sugar, Wafer", 1.25),
                ("Mocha Frappe", "Drink", "Coffee, Milk, Chocolate, Ice", 3.99),
                ("Bottled Water", "Drink", "Water", 1.50),
                ("Sprite", "Drink", "Sugar, Water, Carbonation", 1.99),
                ("McFlurry", "Side", "Milk, Oreo, Sugar", 3.29),
                ("Blueberry Muffin", "Side", "Blueberry, Flour, Sugar, Egg", 2.75)
            ]
            for name, cat, ing, prc in menu_data:
                db.session.add(FoodItem(name=name, category=cat, ingredients=ing, price=prc))
            db.session.commit()
    app.run(debug=True)