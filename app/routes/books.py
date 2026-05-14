from flask import Blueprint, render_template, request, redirect, session
from app import db
from app.models import Book

books_bp = Blueprint('books', __name__)

@books_bp.route('/')
def home():
    return redirect('/dashboard')

@books_bp.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')
    books = Book.query.all()
    return render_template('dashboard.html', user=session['user'], books=books)

@books_bp.route('/create', methods=['GET', 'POST'])
def create():
    if 'user' not in session:
        return redirect('/login')
    if request.method == 'POST':
        new_book = Book(
            title=request.form['title'],
            author=request.form['author'],
            stock=int(request.form['stock']),
            price=float(request.form['price']),
            description=request.form['description'],
            category=request.form['category']
        )
        db.session.add(new_book)
        db.session.commit()
        return redirect('/dashboard')
    return render_template('create.html')

@books_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    if 'user' not in session:
        return redirect('/login')
    book = Book.query.get_or_404(id)
    if request.method == 'POST':
        book.title = request.form['title']
        book.author = request.form['author']
        book.stock = int(request.form['stock'])
        book.price = float(request.form['price'])
        book.description = request.form['description']
        book.category = request.form['category']
        db.session.commit()
        return redirect('/dashboard')
    return render_template('edit.html', book=book)

@books_bp.route('/delete/<int:id>')
def delete(id):
    if 'user' not in session:
        return redirect('/login')
    book = Book.query.get_or_404(id)
    db.session.delete(book)
    db.session.commit()
    return redirect('/dashboard')
