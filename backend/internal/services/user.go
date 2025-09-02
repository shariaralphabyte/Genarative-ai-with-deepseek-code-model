package services

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"chatgpt-system/internal/models"

	"github.com/golang-jwt/jwt/v5"
	"github.com/google/uuid"
	"golang.org/x/crypto/bcrypt"
)

type UserService struct {
	db *sql.DB
}

func NewUserService(db *sql.DB) *UserService {
	return &UserService{db: db}
}

func (us *UserService) Register(ctx context.Context, email, username, password string) (*models.User, error) {
	// Hash password
	hashedPassword, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return nil, fmt.Errorf("failed to hash password: %w", err)
	}

	user := models.User{
		ID:               uuid.New(),
		Email:            email,
		Username:         username,
		PasswordHash:     string(hashedPassword),
		SubscriptionTier: "free",
		CreatedAt:        time.Now(),
		UpdatedAt:        time.Now(),
		IsActive:         true,
	}

	query := `
		INSERT INTO users (id, email, username, password_hash, subscription_tier, created_at, updated_at, is_active)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`

	_, err = us.db.ExecContext(ctx, query,
		user.ID, user.Email, user.Username, user.PasswordHash,
		user.SubscriptionTier, user.CreatedAt, user.UpdatedAt, user.IsActive)

	if err != nil {
		return nil, fmt.Errorf("failed to create user: %w", err)
	}

	return &user, nil
}

func (us *UserService) Login(ctx context.Context, email, password, jwtSecret string, jwtExpiry time.Duration) (string, *models.User, error) {
	var user models.User
	query := `
		SELECT id, email, username, password_hash, subscription_tier, created_at, updated_at, last_login, is_active
		FROM users
		WHERE email = $1 AND is_active = true`

	err := us.db.QueryRowContext(ctx, query, email).Scan(
		&user.ID, &user.Email, &user.Username, &user.PasswordHash,
		&user.SubscriptionTier, &user.CreatedAt, &user.UpdatedAt,
		&user.LastLogin, &user.IsActive)

	if err != nil {
		if err == sql.ErrNoRows {
			return "", nil, fmt.Errorf("user not found")
		}
		return "", nil, fmt.Errorf("failed to get user: %w", err)
	}

	// Verify password
	if err := bcrypt.CompareHashAndPassword([]byte(user.PasswordHash), []byte(password)); err != nil {
		return "", nil, fmt.Errorf("invalid password")
	}

	// Update last login
	now := time.Now()
	_, err = us.db.ExecContext(ctx, "UPDATE users SET last_login = $1 WHERE id = $2", now, user.ID)
	if err != nil {
		return "", nil, fmt.Errorf("failed to update last login: %w", err)
	}
	user.LastLogin = &now

	// Generate JWT token
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, jwt.MapClaims{
		"user_id":  user.ID.String(),
		"username": user.Username,
		"email":    user.Email,
		"exp":      time.Now().Add(jwtExpiry).Unix(),
	})

	tokenString, err := token.SignedString([]byte(jwtSecret))
	if err != nil {
		return "", nil, fmt.Errorf("failed to generate token: %w", err)
	}

	return tokenString, &user, nil
}

func (us *UserService) GetUserByID(ctx context.Context, userID uuid.UUID) (*models.User, error) {
	var user models.User
	query := `
		SELECT id, email, username, subscription_tier, created_at, updated_at, last_login, is_active
		FROM users
		WHERE id = $1 AND is_active = true`

	err := us.db.QueryRowContext(ctx, query, userID).Scan(
		&user.ID, &user.Email, &user.Username, &user.SubscriptionTier,
		&user.CreatedAt, &user.UpdatedAt, &user.LastLogin, &user.IsActive)

	if err != nil {
		return nil, err
	}

	return &user, nil
}
