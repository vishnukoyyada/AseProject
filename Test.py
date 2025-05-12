class Solution:
    def __init__(self,nums):
        self.num = nums

    def minimumSum(self) -> int:
        digits = sorted([int(d) for d in str(self.num)])

        print(digits)
        # To minimize sum, pair smallest with smallest: e.g. 2+3 and 2+9 = 22 + 39 = 61
        num1 = digits[0] * 10 + digits[2]
        num2 = digits[1] * 10 + digits[3]
        return num1 + num2

sol = Solution(2323)
print(sol.minimumSum())
