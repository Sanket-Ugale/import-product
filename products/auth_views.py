"""
Authentication views for JWT token management and login.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login as django_login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.status import HTTP_401_UNAUTHORIZED, HTTP_200_OK
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with user info."""
    
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token['user_id'] = user.id
        token['username'] = user.username
        token['email'] = user.email
        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token obtain view."""
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = (AllowAny,)


class LogoutView(APIView):
    """Logout view to blacklist refresh token."""
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh_token")
            if not refresh_token:
                return Response(
                    {"error": "Refresh token is required"},
                    status=HTTP_401_UNAUTHORIZED
                )
            
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            return Response(
                {"message": "Successfully logged out"},
                status=HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=HTTP_401_UNAUTHORIZED
            )


def login_page(request):
    """Render login page."""
    if request.user.is_authenticated:
        return redirect('products:list')
    
    error_message = None
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            django_login(request, user)
            return redirect('products:list')
        else:
            error_message = "Invalid username or password"
    
    context = {
        'error_message': error_message,
    }
    return render(request, 'auth/login.html', context)


@login_required(login_url='login')
def get_token_page(request):
    """Page to display JWT tokens for API access."""
    try:
        refresh = RefreshToken.for_user(request.user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
    except Exception as e:
        access_token = None
        refresh_token = None
        error = str(e)
    
    context = {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': request.user,
    }
    return render(request, 'auth/tokens.html', context)


@require_http_methods(["GET", "POST"])
def logout(request):
    """Logout user."""
    from django.contrib.auth import logout as django_logout
    django_logout(request)
    return redirect('login')
