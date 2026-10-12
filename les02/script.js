function twoSum(nums, target) {
    const arr = nums.map((num, index) => [num, index]);
    arr.sort((a, b) => a[0] - b[0]);

    let left = 0;
    let right = arr.length - 1;

    while (left < right) {
        const sum = arr[left][0] + arr[right][0];

        if (sum == target) {
            const i = arr[left][1];
            const j = arr[right][1];

            return i < j ? [i, j] : [j, i];
        }

        if (sum < target) {
            left++;
        } else {
            right--;
        }
    }
}
console.log(twoSum([3, 2, 4], 6))