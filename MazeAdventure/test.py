


def gcd(a, b):
    return a if b == 0 else gcd(b, a%b)

g = gcd(2388, 1668)
print(2388//g, 1668//g)




