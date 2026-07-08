from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from .forms import SignUpForm, UserProfileForm
from .models import UserProfile

@require_http_methods(["GET", "POST"])
def signup(request):
    """User registration view"""
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            UserProfile.objects.create(user=user)
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('dashboard')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})

@require_http_methods(["GET", "POST"])
def login_view(request):
    """User login view"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'accounts/login.html', {'error': 'Invalid credentials'})
    return render(request, 'accounts/login.html')

@require_http_methods(["GET"])
def logout_view(request):
    """User logout view"""
    logout(request)
    return redirect('accounts:login')

@login_required(login_url='accounts:login')
@require_http_methods(["GET", "POST"])
def profile(request):
    """User profile view"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=profile)
    return render(request, 'accounts/profile.html', {'form': form, 'profile': profile})
