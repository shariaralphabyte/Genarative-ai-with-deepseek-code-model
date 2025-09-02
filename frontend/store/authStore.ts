import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import axios from 'axios'

interface User {
  id: string
  email: string
  username: string
  subscription_tier: string
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, username: string, password: string) => Promise<void>
  logout: () => void
  checkAuth: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (email: string, password: string) => {
        try {
          const response = await axios.post('/api/auth/login', {
            email,
            password,
          })

          const { token, user } = response.data
          
          set({
            user,
            token,
            isAuthenticated: true,
          })

          // Set default authorization header
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
        } catch (error) {
          throw new Error('Login failed')
        }
      },

      register: async (email: string, username: string, password: string) => {
        try {
          await axios.post('/api/auth/register', {
            email,
            username,
            password,
          })
        } catch (error) {
          throw new Error('Registration failed')
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        })
        delete axios.defaults.headers.common['Authorization']
      },

      checkAuth: async () => {
        const { token } = get()
        if (token) {
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
          set({ isAuthenticated: true })
        } else {
          set({ isAuthenticated: false })
        }
      },
    }),
    {
      name: 'auth-storage',
    }
  )
)
